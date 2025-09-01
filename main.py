#!/usr/bin/env python3
"""
main.py - Tkinter GUI for extended YTP generator using ffmpeg

Updated to handle early ffmpeg detection errors and show clearer messages.
"""

import os
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ffmpeg_worker import FFmpegWorker, RuntimeError as FFmpegInitError
from effects import EFFECTS_METADATA
from assets import gather_assets
from utils import open_with_default_app, find_executable

APP_TITLE = "YTP Generator - Extended Assets (Tk GUI + ffmpeg)"
DEFAULT_PREVIEW_DURATION = 10  # seconds


class EffectRow:
    def __init__(self, parent, key, metadata, on_change):
        self.key = key
        self.metadata = metadata
        self.on_change = on_change

        self.frame = ttk.Frame(parent)
        self.enabled_var = tk.BooleanVar(value=False)
        self.prob_var = tk.DoubleVar(value=1.0)
        self.level_var = tk.DoubleVar(value=metadata.get("default_level", 1.0))

        self.checkbox = ttk.Checkbutton(self.frame, text=metadata["name"], variable=self.enabled_var,
                                        command=self.on_change)
        self.checkbox.grid(row=0, column=0, sticky="w")

        ttk.Label(self.frame, text="prob:").grid(row=0, column=1, sticky="e")
        self.prob_spin = ttk.Spinbox(self.frame, from_=0.0, to=1.0, increment=0.05, textvariable=self.prob_var,
                                     width=5, command=self.on_change)
        self.prob_spin.grid(row=0, column=2, sticky="w")

        ttk.Label(self.frame, text="level:").grid(row=0, column=3, sticky="e")
        self.level_scale = ttk.Scale(self.frame, from_=0.0, to=metadata.get("max_level", 5.0),
                                     variable=self.level_var, orient="horizontal", command=lambda e: self.on_change())
        self.level_scale.grid(row=0, column=4, sticky="we", padx=(5, 0))
        self.frame.columnconfigure(4, weight=1)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def get_config(self):
        return {
            "enabled": self.enabled_var.get(),
            "probability": float(self.prob_var.get()),
            "level": float(self.level_var.get()),
        }


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.minsize(920, 560)

        self.source_file = None
        self.overlay_file = None
        self.preview_duration = tk.IntVar(value=DEFAULT_PREVIEW_DURATION)
        self.output_dir = tk.StringVar(value=os.path.join(os.getcwd(), "outputs"))

        # asset directories
        self.asset_dirs = {
            "images": tk.StringVar(value=""),
            "memes": tk.StringVar(value=""),
            "meme_sounds": tk.StringVar(value=""),
            "sounds": tk.StringVar(value=""),
            "overlays_videos": tk.StringVar(value=""),
            "adverts": tk.StringVar(value=""),
            "errors": tk.StringVar(value=""),
        }

        self.effect_rows = {}
        self.worker = None
        self.preview_btn = None
        self.generate_btn = None

        # create UI early (so we can disable buttons if ffmpeg missing)
        self.create_widgets()

        # attempt to initialize ffmpeg worker and handle errors clearly
        try:
            self.worker = FFmpegWorker()
            # good: ffmpeg found; enable buttons if they were disabled
            if self.preview_btn:
                self.preview_btn.configure(state="normal")
            if self.generate_btn:
                self.generate_btn.configure(state="normal")
            self.log("ffmpeg detected on PATH.")
        except Exception as e:
            # disable operations that require ffmpeg
            if self.preview_btn:
                self.preview_btn.configure(state="disabled")
            if self.generate_btn:
                self.generate_btn.configure(state="disabled")
            messagebox.showerror("FFmpeg not found", str(e))
            self.log("FFmpeg initialization error:", e)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # top frame: file selection
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=8, pady=6)

        ttk.Label(top, text="Source:").grid(row=0, column=0, sticky="w")
        self.src_label = ttk.Label(top, text="(none)", width=60)
        self.src_label.grid(row=0, column=1, sticky="w")
        ttk.Button(top, text="Choose File", command=self.choose_source).grid(row=0, column=2, sticky="e")

        ttk.Label(top, text="Overlay (PNG/GIF):").grid(row=1, column=0, sticky="w")
        self.ov_label = ttk.Label(top, text="(none)", width=60)
        self.ov_label.grid(row=1, column=1, sticky="w")
        ttk.Button(top, text="Choose Overlay", command=self.choose_overlay).grid(row=1, column=2, sticky="e")

        ttk.Label(top, text="Output dir:").grid(row=2, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.output_dir, width=60).grid(row=2, column=1, sticky="we")
        ttk.Button(top, text="Browse", command=self.browse_output).grid(row=2, column=2, sticky="e")

        # assets directories
        asset_frame = ttk.LabelFrame(self, text="Asset Folders (optional)")
        asset_frame.pack(side="top", fill="x", padx=8, pady=(0, 6))
        r = 0
        for key in self.asset_dirs:
            ttk.Label(asset_frame, text=key.replace("_", " ").title() + ":").grid(row=r, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(asset_frame, textvariable=self.asset_dirs[key], width=70).grid(row=r, column=1, sticky="we", padx=4, pady=2)
            ttk.Button(asset_frame, text="Browse", command=lambda k=key: self.browse_asset_dir(k)).grid(row=r, column=2, sticky="e", padx=4, pady=2)
            r += 1

        # main area: effects + controls
        center = ttk.Frame(self)
        center.pack(side="top", fill="both", expand=True, padx=8, pady=6)

        left_panel = ttk.LabelFrame(center, text="Effects")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 4))

        canvas = tk.Canvas(left_panel)
        scrollbar = ttk.Scrollbar(left_panel, orient="vertical", command=canvas.yview)
        effects_frame = ttk.Frame(canvas)

        effects_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=effects_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i, (key, meta) in enumerate(EFFECTS_METADATA.items()):
            row = EffectRow(effects_frame, key, meta, self.on_effect_change)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            self.effect_rows[key] = row

        # right panel: controls + preview + log
        right_panel = ttk.LabelFrame(center, text="Controls")
        right_panel.pack(side="left", fill="both", expand=True)

        ttk.Label(right_panel, text="Preview duration (s):").pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Spinbox(right_panel, from_=3, to=120, textvariable=self.preview_duration, width=6).pack(anchor="w", padx=8)

        btn_frame = ttk.Frame(right_panel)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.preview_btn = ttk.Button(btn_frame, text="Preview (fast)", command=self.on_preview)
        self.preview_btn.pack(side="left", padx=4)
        self.generate_btn = ttk.Button(btn_frame, text="Generate YTP", command=self.on_generate)
        self.generate_btn.pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Open Output Folder", command=self.open_output_dir).pack(side="left", padx=4)

        # log
        log_frame = ttk.LabelFrame(right_panel, text="Progress / Log")
        log_frame.pack(fill="both", expand=True, padx=8, pady=6)
        self.log_text = tk.Text(log_frame, height=20, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def log(self, *args, sep=" ", end="\n"):
        msg = sep.join(str(a) for a in args) + end
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def choose_source(self):
        path = filedialog.askopenfilename(title="Choose source video",
                                          filetypes=[("Video files", "*.mp4 *.mov *.mkv *.avi"), ("All files", "*.*")])
        if path:
            self.source_file = path
            self.src_label.config(text=os.path.basename(path))
            self.log("Selected source:", path)

    def choose_overlay(self):
        path = filedialog.askopenfilename(title="Choose overlay image/gif",
                                          filetypes=[("Image/GIF", "*.png *.gif *.webp"), ("All files", "*.*")])
        if path:
            self.overlay_file = path
            self.ov_label.config(text=os.path.basename(path))
            self.log("Selected overlay:", path)

    def browse_output(self):
        path = filedialog.askdirectory(title="Choose output directory")
        if path:
            self.output_dir.set(path)
            self.log("Output dir:", path)

    def browse_asset_dir(self, key):
        path = filedialog.askdirectory(title=f"Choose folder for {key}")
        if path:
            self.asset_dirs[key].set(path)
            self.log(f"Set {key} folder:", path)

    def open_output_dir(self):
        open_with_default_app(self.output_dir.get())

    def on_effect_change(self):
        # for future dynamic UI updates
        pass

    def gather_config(self):
        effect_configs = {}
        for key, row in self.effect_rows.items():
            cfg = row.get_config()
            effect_configs[key] = cfg

        # scan asset dirs into simple dict of lists
        assets = {}
        for k, var in self.asset_dirs.items():
            v = var.get().strip()
            assets[k] = gather_assets(v) if v else []

        return {
            "src": self.source_file,
            "overlay": self.overlay_file,
            "output_dir": self.output_dir.get(),
            "preview_duration": int(self.preview_duration.get()),
            "effects": effect_configs,
            "assets": assets
        }

    def on_preview(self):
        cfg = self.gather_config()
        if not cfg["src"]:
            messagebox.showwarning("No source", "Please select a source video first.")
            return
        threading.Thread(target=self._run_preview_thread, args=(cfg,), daemon=True).start()

    def _run_preview_thread(self, cfg):
        self.log("Starting preview...")
        try:
            out_path = self.worker.generate_preview(cfg, self.log)
            if out_path:
                self.log("Preview ready:", out_path)
                open_with_default_app(out_path)  # open with default app or ffplay
        except Exception as e:
            # show more detail and suggest manual ffmpeg run
            self.log("Preview failed:", e)
            messagebox.showerror("Preview failed", "Preview failed: {}\n\nTip: copy the FFmpeg command from the log and run it manually in a command prompt to see ffmpeg's error output.".format(e))

    def on_generate(self):
        cfg = self.gather_config()
        if not cfg["src"]:
            messagebox.showwarning("No source", "Please select a source video first.")
            return
        base = os.path.splitext(os.path.basename(cfg["src"]))[0]
        out_name = f"{base}_ytp_{int(time.time())}.mp4"
        out_path = os.path.join(cfg["output_dir"], out_name)
        threading.Thread(target=self._run_generate_thread, args=(cfg, out_path), daemon=True).start()

    def _run_generate_thread(self, cfg, out_path):
        self.log("Starting generation:", out_path)
        try:
            self.worker.generate(cfg, out_path, self.log)
            self.log("Generation finished:", out_path)
            messagebox.showinfo("Done", f"Generated: {out_path}")
        except Exception as e:
            self.log("Generation failed:", e)
            messagebox.showerror("Error", f"Generation failed: {e}\n\nCheck the log for the FFmpeg command and errors.")

    def on_close(self):
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
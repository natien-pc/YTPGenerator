"""
ffmpeg_worker.py - Build and run ffmpeg commands for selected effects.

Changes:
- Preflight checks for ffmpeg binary using utils.find_executable.
- Validates input files exist before executing ffmpeg.
- More informative errors when ffmpeg not found or files missing.
- Uses normalized exit-code reporting from utils.run_subprocess.
"""

import os
import tempfile
import random
import shutil

from effects import EFFECTS_METADATA, build_effect_command_for
from utils import run_subprocess, find_executable

class FFmpegWorker:
    def __init__(self, ffmpeg_bin="ffmpeg", ffplay_bin="ffplay"):
        # prefer explicit provided value, otherwise locate on PATH
        self.requested_ffmpeg = ffmpeg_bin
        self.requested_ffplay = ffplay_bin

        self.ffmpeg = find_executable(self.requested_ffmpeg) or self.requested_ffmpeg
        self.ffplay = find_executable(self.requested_ffplay) or self.requested_ffplay

        # If ffmpeg isn't a path to an executable, try which; otherwise raise informative error.
        if not find_executable(self.ffmpeg):
            raise RuntimeError(
                "ffmpeg executable not found. Please install ffmpeg and ensure 'ffmpeg' is on your PATH, "
                "or place ffmpeg.exe in the project folder. You can test by running 'ffmpeg -version' in a command prompt."
            )

    def _verify_files_exist(self, src_path, extra_inputs):
        """
        Ensure that source and extra inputs exist before calling ffmpeg.
        Raises RuntimeError with details for any missing file.
        """
        missing = []
        if not src_path or not os.path.isfile(src_path):
            missing.append(("source", src_path))
        for p in extra_inputs or []:
            if not p or not os.path.isfile(p):
                missing.append(("extra", p))
        if missing:
            msgs = []
            for kind, path in missing:
                msgs.append("{} file not found: {!r}".format(kind, path))
            raise RuntimeError("Missing input files:\n" + "\n".join(msgs))

    def _assemble_filter_complex(self, src_path, overlay_path, chosen_effects, assets):
        """
        Build a filter_complex string and additional inputs list based on chosen_effects.
        Effects return filters with placeholders {0v}/{0a} etc.; worker will map to global inputs.
        """
        extra_inputs = []
        filters = []
        global_input_offset = 1  # 0 is main source

        for key in EFFECTS_METADATA.keys():
            cfg = chosen_effects.get(key, {})
            if not cfg or not cfg.get("enabled"):
                continue
            p = float(cfg.get("probability", 1.0))
            if p < 1.0 and random.random() > p:
                continue
            level = float(cfg.get("level", EFFECTS_METADATA[key].get("default_level", 1.0)))

            cmd = build_effect_command_for(key, level, src_path, overlay_path, assets)
            if not cmd:
                continue
            this_effect_start_index = global_input_offset
            for inp in cmd.get("inputs", []):
                extra_inputs.append(inp)
                global_input_offset += 1
            # Replace placeholders
            for fragment in cmd.get("filters", []):
                frag = fragment
                frag = frag.replace("{0v}", "[0:v]").replace("{0a}", "[0:a]")
                num_local = len(cmd.get("inputs", []))
                for j in range(1, num_local + 1):
                    global_idx = this_effect_start_index + (j - 1)
                    frag = frag.replace("{" + str(j) + "v}", f"[{global_idx}:v]")
                    frag = frag.replace("{" + str(j) + "a}", f"[{global_idx}:a]")
                filters.append(frag)

        if not filters:
            filters = ["[0:v]copy[vout]", "[0:a]anull[aout]"]
        filter_complex = "; ".join(filters)
        return extra_inputs, filter_complex

    def generate_preview(self, cfg, log_fn=print):
        src = cfg["src"]
        overlay = cfg.get("overlay")
        duration = int(cfg.get("preview_duration", 8))
        chosen = cfg["effects"]
        assets = cfg.get("assets", {})

        tmpdir = tempfile.mkdtemp(prefix="ytp_preview_")
        out_path = os.path.join(tmpdir, "preview.mp4")

        extra_inputs, filter_complex = self._assemble_filter_complex(src, overlay, chosen, assets)
        # verify that files exist
        self._verify_files_exist(src, extra_inputs)

        cmd = [self.ffmpeg, "-y", "-ss", "0", "-t", str(duration), "-i", src]
        for inp in extra_inputs:
            cmd.extend(["-i", inp])
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]"])
        cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-shortest", out_path])

        log_fn("Preview FFmpeg command:", " ".join(cmd))
        run_subprocess(cmd, log_fn)
        return out_path

    def generate(self, cfg, out_path, log_fn=print):
        src = cfg["src"]
        overlay = cfg.get("overlay")
        chosen = cfg["effects"]
        assets = cfg.get("assets", {})

        tmpdir = tempfile.mkdtemp(prefix="ytp_build_")
        extra_inputs, filter_complex = self._assemble_filter_complex(src, overlay, chosen, assets)
        self._verify_files_exist(src, extra_inputs)

        cmd = [self.ffmpeg, "-y", "-i", src]
        for inp in extra_inputs:
            cmd.extend(["-i", inp])
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]"])
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", out_path])

        log_fn("FFmpeg command:", " ".join(cmd))
        run_subprocess(cmd, log_fn)
        return out_path
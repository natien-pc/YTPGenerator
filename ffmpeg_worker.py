"""
ffmpeg_worker.py - Build and run ffmpeg commands for selected effects.

This updated worker supports an 'assets' dict passed from the GUI and a simple
placeholder replacement mechanism for mapping per-effect relative inputs to
global ffmpeg input indices.

Each effect should return filters using placeholders like {0v}, {1v}, {0a}, {1a}
where {0v}/{0a} always refers to the main source ([0:v]/[0:a]) and {1v} refers
to the first extra input added by that effect, etc. The worker will map those
placeholders to the correct global input indexes when assembling filter_complex.
"""

import os
import tempfile
import subprocess
import random
from effects import EFFECTS_METADATA, build_effect_command_for
from utils import run_subprocess


class FFmpegWorker:
    def __init__(self, ffmpeg_bin="ffmpeg", ffplay_bin="ffplay"):
        self.ffmpeg = ffmpeg_bin
        self.ffplay = ffplay_bin

    def _assemble_filter_complex(self, src_path, overlay_path, chosen_effects, assets):
        """
        Build a filter_complex string and additional inputs list based on chosen_effects.
        Effects should use placeholders {0v},{0a} for main input and {1v},{1a} ... for their extra inputs.
        Returns: (extra_inputs_list, filter_complex)
        """
        extra_inputs = []  # global list of extra input file paths
        filters = []
        global_input_offset = 1  # next global index for extra inputs (0 reserved for main source)

        # For deterministic ordering, iterate in EFFECTS_METADATA order
        for key in EFFECTS_METADATA.keys():
            cfg = chosen_effects.get(key, {})
            if not cfg or not cfg.get("enabled"):
                continue
            # probability check
            p = float(cfg.get("probability", 1.0))
            if p < 1.0 and random.random() > p:
                continue
            level = float(cfg.get("level", EFFECTS_METADATA[key].get("default_level", 1.0)))

            cmd = build_effect_command_for(key, level, src_path, overlay_path, assets)
            if not cmd:
                continue
            # cmd: { "inputs": [...], "filters": [...], "label": "vout" }
            # Record current offset for this effect
            this_effect_start_index = global_input_offset
            # append its inputs to global list and increment offset
            for inp in cmd.get("inputs", []):
                extra_inputs.append(inp)
                global_input_offset += 1
            # Replace placeholders in filters: {0v}->{0:v}, {1v}->{N:v} etc.
            for fragment in cmd.get("filters", []):
                frag = fragment
                # find placeholders like {0v}, {1a}
                # replace {0v} with [0:v], {0a} with [0:a]
                frag = frag.replace("{0v}", "[0:v]").replace("{0a}", "[0:a]")
                # for each local extra input index j, replace {jv}/{ja}
                num_local_inputs = len(cmd.get("inputs", []))
                for j in range(1, num_local_inputs + 1):
                    global_idx = this_effect_start_index + (j - 1)
                    frag = frag.replace("{" + str(j) + "v}", f"[{global_idx}:v]")
                    frag = frag.replace("{" + str(j) + "a}", f"[{global_idx}:a]")
                filters.append(frag)
        # Ensure there's at least a passthrough if no filters
        if not filters:
            filters = ["[0:v]copy[vout]", "[0:a]anull[aout]"]
        # Guarantee that some filters produce [vout] and [aout]; if not present, try to append mapping
        fc = "; ".join(filters)
        return extra_inputs, fc

    def generate_preview(self, cfg, log_fn=print):
        """
        Create a short preview using preview duration and chosen effects.
        Writes to temp file and returns path to preview file.
        """
        src = cfg["src"]
        overlay = cfg.get("overlay")
        duration = int(cfg.get("preview_duration", 8))
        chosen = cfg["effects"]
        assets = cfg.get("assets", {})

        tmpdir = tempfile.mkdtemp(prefix="ytp_preview_")
        out_path = os.path.join(tmpdir, "preview.mp4")
        extra_inputs, filter_complex = self._assemble_filter_complex(src, overlay, chosen, assets)

        cmd = [self.ffmpeg, "-y", "-ss", "0", "-t", str(duration), "-i", src]
        for inp in extra_inputs:
            cmd.extend(["-i", inp])
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex])
            # attempt to map outputs if filters produced named outputs
            cmd.extend(["-map", "[vout]", "-map", "[aout]"])
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

        cmd = [self.ffmpeg, "-y", "-i", src]
        for inp in extra_inputs:
            cmd.extend(["-i", inp])
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex])
            # try to map vout/aout produced by filters
            cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", out_path])

        log_fn("FFmpeg command:", " ".join(cmd))
        run_subprocess(cmd, log_fn)
        return out_path
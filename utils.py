"""
utils.py - helper utilities for running subprocesses, file dialogs, and opening files.
"""

import subprocess
import os
import sys

def run_subprocess(cmd, log_fn=print):
    """
    Run a subprocess command while streaming stdout/stderr to log_fn.
    Compatible with Windows. cmd must be a list.
    """
    log_fn("Running:", " ".join(cmd))
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    except FileNotFoundError as e:
        raise RuntimeError("FFmpeg binary not found. Ensure ffmpeg is installed and on PATH.") from e

    for line in iter(process.stdout.readline, ""):
        if line:
            log_fn(line.rstrip())
    process.stdout.close()
    rc = process.wait()
    if rc != 0:
        raise RuntimeError(f"Process exited with code {rc}")

def open_with_default_app(path):
    """
    Open a file or folder with the platform default application.
    Works on Windows (os.startfile), macOS (open), Linux (xdg-open).
    """
    if os.path.isdir(path):
        # open folder
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return
    if not os.path.exists(path):
        return
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
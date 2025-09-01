"""
utils.py - helper utilities for running subprocesses, file dialogs, and opening files.

Improvements:
- find_executable() helper (shutil.which wrapper).
- run_subprocess() normalizes Windows unsigned exit codes and raises clearer errors.
"""

import subprocess
import os
import sys
import shutil

def find_executable(name):
    """
    Return full path to executable if found on PATH, otherwise None.
    Wrapper around shutil.which for easier testing.
    """
    return shutil.which(name)

def _normalize_return_code(rc):
    """
    Convert unsigned 32-bit return codes (as sometimes seen on Windows) to signed int.
    Example: 4294967294 -> -2
    """
    if rc is None:
        return None
    try:
        rc = int(rc)
    except Exception:
        return rc
    if rc >= 2**31:
        # convert from unsigned 32-bit to signed
        rc_signed = rc - 2**32
        return rc_signed
    return rc

def run_subprocess(cmd, log_fn=print, cwd=None):
    """
    Run a subprocess command while streaming stdout/stderr to log_fn.
    - cmd must be a list.
    - Raises RuntimeError with helpful message if the executable is missing or exit non-zero.
    """
    log_fn("Running:", " ".join(cmd))
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd=cwd)
    except FileNotFoundError as e:
        # Typically this means the executable (ffmpeg) wasn't found.
        raise RuntimeError("Executable not found: {}. Ensure it is installed and available on PATH.".format(cmd[0])) from e
    except OSError as e:
        # Some other OS error
        raise RuntimeError("Failed to start process {}: {}".format(cmd[0], e)) from e

    # Stream lines to log function
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                log_fn(line.rstrip())
    except Exception as e:
        # Make sure we don't leave zombie processes
        try:
            process.kill()
        except Exception:
            pass
        raise

    process.stdout.close()
    rc = process.wait()
    rc_signed = _normalize_return_code(rc)
    if rc != 0:
        raise RuntimeError("Process exited with code {} (interpreted as {}). See log above for ffmpeg errors.".format(rc, rc_signed))

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
"""
assets.py - helpers to gather asset lists from directories.

Given a folder path, gather assets by common extensions for images, audio, and video.
Returns simple lists of file paths to be picked by effects.
"""

import os

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
AUDIO_EXTS = (".mp3", ".wav", ".aac", ".m4a", ".ogg")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi")

def gather_assets(dirpath):
    """
    Return a list of file paths inside dirpath. Walks top-level only.
    """
    if not dirpath:
        return []
    if not os.path.isdir(dirpath):
        return []
    files = []
    for entry in os.listdir(dirpath):
        full = os.path.join(dirpath, entry)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext in IMAGE_EXTS + AUDIO_EXTS + VIDEO_EXTS:
            files.append(full)
    return sorted(files)
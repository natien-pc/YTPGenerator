# YTP Generator - Extended Assets (Tkinter + FFmpeg)

This project is an extended scaffold for a "YouTube Poop (YTP)" style generator built in Python with Tkinter and ffmpeg.
It targets compatibility with older Windows systems (e.g., Windows 8.1) and uses external ffmpeg/ffplay binaries.

What's new in this update
- Added support for asset folders:
  - images
  - memes
  - meme_sounds
  - sounds
  - overlays_videos
  - adverts
  - errors
- New effects that can consume those assets:
  - adverts (overlay advert videos)
  - errors (glitch/error overlays)
  - images (image montage/injection)
  - meme_sounds (play short meme audio overlays)
  - memes (overlay meme images and optionally mix meme sounds)
  - overlay_videos (overlay short video clips)
  - sounds (mix sounds into the main audio)
- GUI: choose asset folders from the Assets panel. Effects can randomly select assets from those folders.
- Worker: improved placeholder-based filter mapping so effects can add extra input files without hardcoding global input indices.
- assets.py: helper to scan directories for supported media files.

Files
- main.py - Tkinter GUI (choose source, overlays, asset folders; toggle effects; preview/generate)
- ffmpeg_worker.py - builds filter_complex and runs ffmpeg (handles placeholder mapping)
- effects.py - per-effect definitions and filter fragments using placeholders
- assets.py - gather files from asset folders
- utils.py - subprocess runner + open file helper

Requirements
- Python 3.6+
- ffmpeg installed and available on PATH (ffplay optional)
- Windows 8.1 compatible (pure Python + subprocess)

Usage
1. Put `ffmpeg.exe` (and optionally `ffplay.exe`) on PATH or in the project folder.
2. Create folders with assets (images, memes, meme_sounds, sounds, overlays_videos, adverts, errors).
3. Run: `python main.py`
4. Choose a source video, optionally an overlay, set asset directories, toggle effects, and press Preview or Generate.

Notes & Limitations
- The filter fragments use a simple placeholder system handled by the worker. This is convenient for scaffolding but not a replacement for a full stream-label manager.
- Many audio pitch/time manipulations are approximations using ffmpeg filters (asetrate, atempo). For high-quality pitch correction or time-stretching, consider external tools.
- If multiple effects try to produce both [vout] and [aout] the last ones will take precedence; for complex chained effects you may want to implement explicit stream label chaining in ffmpeg_worker.
- The GUI is intentionally simple to keep compatibility with older Windows and to be easy to extend.

Next development ideas
- Implement a stream label manager to chain multiple effects robustly (v0->v1->v2...).
- Add a preview embedded player (ffplay window or a lightweight video widget).
- Add presets, save/load project files, and drag-and-drop asset management.
- Implement deterministic timelines to place adverts/explosions exactly.

Be careful with "earrape" and other loud effects — they will be very loud.

Have fun extending and testing with small sample videos and assets!
```

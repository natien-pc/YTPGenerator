"""
effects.py - Definitions and builders for individual effects.

Updated to support asset-driven effects:
- adverts: overlay a short advert video at start or in the middle (from assets['adverts'])
- errors: glitch/error overlay images/videos (assets['errors'])
- images: simple image injection / montage (assets['images'])
- meme_sounds: pick meme sounds to overlay (assets['meme_sounds'])
- memes: overlay meme images and play meme sound together (assets['memes'] and meme_sounds)
- overlay_videos: overlay short video clips over main video (assets['overlays_videos'])
- sounds: similar to random_sound but chooses from assets['sounds']

Each returned filter fragment uses placeholders:
{0v}/{0a} => main source ([0:v]/[0:a])
{1v}/{1a}, {2v}/{2a}, ... => first/second/... extra inputs provided by that effect.
ffmpeg_worker will map placeholders to the proper global input indices.
"""

import os
import random
import math

EFFECTS_METADATA = {
    "random_sound": {"name": "Add Random Sound (legacy)", "default_level": 1.0, "max_level": 5.0},
    "sounds": {"name": "Add Sound from Assets", "default_level": 1.0, "max_level": 5.0},
    "reverse": {"name": "Reverse Clip (video & audio)", "default_level": 1.0, "max_level": 1.0},
    "speed": {"name": "Speed Up / Slow Down", "default_level": 1.0, "max_level": 4.0},
    "chorus": {"name": "Chorus Effect (aecho)", "default_level": 0.6, "max_level": 2.0},
    "vibrato": {"name": "Vibrato / Pitch Bend (asetrate+atempo)", "default_level": 1.0, "max_level": 2.0},
    "stutter": {"name": "Stutter Loop", "default_level": 0.5, "max_level": 3.0},
    "earrape": {"name": "Earrape Mode (gain)", "default_level": 6.0, "max_level": 30.0},
    "autotune": {"name": "Auto-Tune Chaos (placeholder)", "default_level": 1.0, "max_level": 1.0},
    "dance_squid": {"name": "Dance & Squidward Mode", "default_level": 1.0, "max_level": 3.0},
    "invert": {"name": "Invert Colors", "default_level": 1.0, "max_level": 1.0},
    "rainbow": {"name": "Rainbow Overlay (user PNG/GIF)", "default_level": 1.0, "max_level": 1.0},
    "mirror": {"name": "Mirror Mode", "default_level": 1.0, "max_level": 1.0},
    "sus": {"name": "Sus Effect (random pitch/tempo)", "default_level": 1.0, "max_level": 3.0},
    "explosion_spam": {"name": "Explosion Spam (repetitive overlays)", "default_level": 2.0, "max_level": 10.0},
    "frame_shuffle": {"name": "Frame Shuffle (placeholder)", "default_level": 1.0, "max_level": 1.0},
    "meme_injection": {"name": "Meme Injection (overlay image/audio)", "default_level": 1.0, "max_level": 3.0},
    "meme_sounds": {"name": "Meme Sounds (assets)", "default_level": 1.0, "max_level": 3.0},
    "memes": {"name": "Memes (images + sounds)", "default_level": 1.0, "max_level": 3.0},
    "sentence_mix": {"name": "Sentence Mixing / Random Cuts", "default_level": 1.0, "max_level": 5.0},
    "adverts": {"name": "Adverts (overlay ad video)", "default_level": 1.0, "max_level": 3.0},
    "errors": {"name": "Error / Glitch Overlays", "default_level": 1.0, "max_level": 3.0},
    "images": {"name": "Image Montage / Injection", "default_level": 1.0, "max_level": 5.0},
    "overlay_videos": {"name": "Overlay Short Videos", "default_level": 1.0, "max_level": 5.0},
}

def _choose_asset(list_assets):
    if not list_assets:
        return None
    return random.choice(list_assets)


def build_effect_command_for(key, level, src_path, overlay_path=None, assets=None):
    assets = assets or {}
    if key == "random_sound":
        # legacy: no external asset, just bump volume
        return {
            "inputs": [],
            "filters": [
                "{0v}copy[vout]",
                f"{0}{0}" if False else "{0a}volume=1.0[aout]"  # keep placeholder style
            ],
        }

    if key == "sounds":
        # pick a sound from assets['sounds'] and mix into audio
        chosen = _choose_asset(assets.get("sounds", []))
        if not chosen:
            # fallback to no-op
            return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}
        # effect will use one extra input {1} -> referenced as {1a}
        # Mix main audio ({0a}) with chosen sound ({1a})
        return {
            "inputs": [chosen],
            "filters": [
                "{0v}copy[vout]",
                "{0a}[maina]; {1a}[in1]; [maina][in1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            ],
        }

    if key == "reverse":
        return {
            "inputs": [],
            "filters": [
                "{0v}reverse[vrev]",
                "{0a}areverse[arev]",
                "[vrev]setpts=PTS-STARTPTS[vout]",
                "[arev]asetpts=PTS-STARTPTS[aout]"
            ],
        }

    if key == "speed":
        factor = max(0.125, min(4.0, level))
        pts = f"{1.0/float(factor)}*PTS"
        # Build atempo chain
        tempos = []
        target = factor
        if target < 0.5:
            t = target
            while t < 0.5:
                tempos.append(0.5)
                t /= 0.5
            tempos.append(round(t, 3))
        else:
            t = target
            while t > 2.0:
                tempos.append(2.0)
                t /= 2.0
            tempos.append(round(t, 3))
        afilter = ",".join("atempo={}".format(x) for x in tempos)
        return {
            "inputs": [],
            "filters": [
                f"{{0v}}setpts={pts}[vout]",
                f"{{0a}}{afilter}[aout]"
            ]
        }

    if key == "chorus":
        delay = int(20 + level * 60)
        decay = max(0.1, min(0.9, 0.2 + level * 0.2))
        aecho = f"aecho=0.8:0.9:{delay}|{delay*2}:{decay}|{decay*0.6}"
        return {
            "inputs": [],
            "filters": [
                "{0v}copy[vout]",
                f"{{0a}}{aecho}[aout]"
            ]
        }

    if key == "vibrato":
        pitch = max(0.5, min(2.0, level))
        asetrate = f"asetrate=44100*{pitch}"
        atempo_factor = 1.0 / pitch
        afilter = f"{asetrate},aresample=44100,atempo={max(0.5, min(2.0, atempo_factor))}"
        return {
            "inputs": [],
            "filters": [
                "{0v}copy[vout]",
                f"{{0a}}{afilter}[aout]"
            ]
        }

    if key == "stutter":
        loop_count = max(2, int(level * 3))
        return {
            "inputs": [],
            "filters": [
                "{0v}trim=0:0.15,setpts=PTS-STARTPTS[vst]",
                f"[vst]loop={loop_count}:1:0[vstl]",
                "{0a}atrim=0:0.15,asetpts=PTS-STARTPTS[ast]",
                f"[ast]aloop=loop={loop_count}:size=2[astl]",
                "[vstl]scale=iw:ih[vout]",
                "[astl]anull[aout]"
            ]
        }

    if key == "earrape":
        gain = max(2.0, min(30.0, level))
        return {
            "inputs": [],
            "filters": [
                "{0v}eq=contrast=1.1:saturation=1.4[vout]",
                f"{{0a}}volume={gain}[aout]"
            ]
        }

    if key == "autotune":
        return {
            "inputs": [],
            "filters": [
                "{0v}copy[vout]",
                "{0a}anull[aout]"
            ]
        }

    if key == "dance_squid":
        zoom = 1.0 + 0.05 * level
        return {
            "inputs": [],
            "filters": [
                f"{{0v}}scale=iw*{zoom}:ih*{zoom},transpose=1,transpose=2,format=yuv420p[vout]",
                "{0a}atempo=1.0[aout]"
            ]
        }

    if key == "invert":
        return {
            "inputs": [],
            "filters": [
                "{0v}negate[vout]",
                "{0a}anull[aout]"
            ]
        }

    if key == "rainbow":
        # use overlay_path if provided, otherwise try assets.images
        if overlay_path and os.path.exists(overlay_path):
            return {
                "inputs": [overlay_path],
                "filters": [
                    "{0v}{1v}overlay=10:10:shortest=1[vout]",
                    "{0a}anull[aout]"
                ]
            }
        chosen = _choose_asset(assets.get("images", []))
        if chosen:
            return {
                "inputs": [chosen],
                "filters": [
                    "{0v}{1v}overlay=10:10:shortest=1[vout]",
                    "{0a}anull[aout]"
                ]
            }
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    if key == "mirror":
        return {
            "inputs": [],
            "filters": [
                "{0v}hflip[vout]",
                "{0a}anull[aout]"
            ]
        }

    if key == "sus":
        return {
            "inputs": [],
            "filters": [
                "{0v}copy[vout]",
                "{0a}anull[aout]"
            ]
        }

    if key == "explosion_spam":
        chosen = _choose_asset(assets.get("images", [])) or overlay_path
        if chosen:
            return {
                "inputs": [chosen],
                "filters": [
                    # place overlay briefly at t=0..0.6
                    "{0v}{1v}overlay=enable='between(t,0,0.6)':x=10:y=10[vtmp]",
                    "[vtmp]copy[vout]",
                    "{0a}anull[aout]"
                ]
            }
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    if key == "frame_shuffle":
        return {
            "inputs": [],
            "filters": [
                "{0v}tblend=all_mode='addition',framestep=1[vout]",
                "{0a}anull[aout]"
            ]
        }

    if key == "meme_injection":
        chosen_img = _choose_asset(assets.get("memes", [])) or overlay_path
        chosen_snd = _choose_asset(assets.get("meme_sounds", []))
        inputs = []
        filters = []
        if chosen_img:
            inputs.append(chosen_img)
            filters.append("{0v}{1v}overlay=W-w-10:H-h-10[vtmp]")
        else:
            filters.append("{0v}copy[vtmp]")
        if chosen_snd:
            inputs.append(chosen_snd)
            # map vtmp to vout and mix audio
            # note: if both image and sound selected the extra inputs count will be 1 or 2
            # We'll produce a mixing command referencing {1a} or {2a} as appropriate in worker
            filters.append("{0a}[maina]; {1a}[sfx]; [maina][sfx]amix=inputs=2:duration=first[aout]")
            filters.append("[vtmp]copy[vout]")
            return {"inputs": inputs, "filters": filters}
        else:
            filters.append("{0a}anull[aout]")
            filters.append("[vtmp]copy[vout]")
            return {"inputs": inputs, "filters": filters}

    if key == "meme_sounds":
        chosen = _choose_asset(assets.get("meme_sounds", []))
        if not chosen:
            return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}
        return {
            "inputs": [chosen],
            "filters": [
                "{0v}copy[vout]",
                "{0a}[maina]; {1a}[sfx]; [maina][sfx]amix=inputs=2:duration=first[aout]"
            ]
        }

    if key == "memes":
        # memes often include both image and sound packaged; we try to choose image from memes and sound from meme_sounds
        chosen_img = _choose_asset(assets.get("memes", []))
        chosen_snd = _choose_asset(assets.get("meme_sounds", []))
        inputs = []
        filters = []
        if chosen_img:
            inputs.append(chosen_img)
            filters.append("{0v}{1v}overlay=10:10:shortest=1[vtmp]")
        else:
            filters.append("{0v}copy[vtmp]")
        if chosen_snd:
            inputs.append(chosen_snd)
            filters.append("{0a}[m]; {1a}[s]; [m][s]amix=inputs=2:duration=first[aout]")
        else:
            filters.append("{0a}anull[aout]")
        filters.append("[vtmp]copy[vout]")
        return {"inputs": inputs, "filters": filters}

    if key == "sentence_mix":
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    if key == "adverts":
        chosen = _choose_asset(assets.get("adverts", []))
        if chosen:
            # overlay ad video on top for a short period using one extra input
            return {
                "inputs": [chosen],
                "filters": [
                    "{0v}{1v}overlay=enable='between(t,0,3)':x=W-w-10:y=10[vtmp]",
                    "[vtmp]copy[vout]",
                    "{0a}anull[aout]"
                ]
            }
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    if key == "errors":
        chosen = _choose_asset(assets.get("errors", []))
        if chosen:
            return {
                "inputs": [chosen],
                "filters": [
                    # overlay glitch/error file in top-left at several short intervals
                    "{0v}{1v}overlay=enable='gt(mod(t,0.8),0.0)':x=0:y=0[vtmp]",
                    "[vtmp]copy[vout]",
                    "{0a}anull[aout]"
                ]
            }
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    if key == "images":
        chosen = _choose_asset(assets.get("images", []))
        if chosen:
            return {
                "inputs": [chosen],
                "filters": [
                    # simple montage: overlay image fading in at 1s
                    "{0v}{1v}overlay=enable='between(t,1,4)':x=main_w/4:y=main_h/4:alpha='if(lt(t,2),0,1)'[vtmp]",
                    "[vtmp]copy[vout]",
                    "{0a}anull[aout]"
                ]
            }
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    if key == "overlay_videos":
        chosen = _choose_asset(assets.get("overlays_videos", []))
        if chosen:
            return {
                "inputs": [chosen],
                "filters": [
                    "{0v}{1v}overlay=10:10:shortest=1[vtmp]",
                    "[vtmp]copy[vout]",
                    "{0a}anull[aout]"
                ]
            }
        return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}

    # default fallback: passthrough
    return {"inputs": [], "filters": ["{0v}copy[vout]", "{0a}anull[aout]"]}
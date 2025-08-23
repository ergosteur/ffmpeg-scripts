#!/usr/bin/env -S python3
"""
pillarbox_to_4x3.py — Auto-crop pillarboxed 16:9 videos back to 4:3.

Requirements:
  - ffmpeg and ffprobe available in PATH

What it does:
  - Probes the input to get width/height, video codec, bitrate, etc.
  - Computes a centered crop to 4:3 (width = round(height * 4/3)) or
    optionally uses ffmpeg's cropdetect to find precise bars.
  - Re-encodes VIDEO with the *same codec family* (e.g., h264 -> libx264,
    hevc -> libx265, vp9 -> libvpx-vp9, etc.).
  - Targets roughly the same bitrate as the source by default (good quality
    parity without needing to guess CRF).
  - Copies ALL other streams as-is: audio, subtitles, data, attachments.
  - Preserves metadata and chapters.

Usage:
  python3 pillarbox_to_4x3.py INPUT.mp4
  python3 pillarbox_to_4x3.py INPUT1.mkv INPUT2.mov -o outdir

Nice options:
  --use-cropdetect      Run a short cropdetect scan to find exact bars
  --scan-seconds N      Seconds to scan for cropdetect (default 15)
  --crf                 Use CRF mode instead of bitrate (e.g. --crf 18)
  --preset PRESET       ffmpeg encoder preset (default 'medium')
  --output, -o DIR      Output directory (default: alongside input)
  --dry-run             Print the ffmpeg command but don’t run it
"""

import argparse
import json
import math
import os
import shlex
import shutil
import subprocess
import threading
import sys
from collections import Counter
from pathlib import Path

# Map input codec names (as seen in ffprobe) to sane encoders
CODEC_MAP = {
    "h264": "libx264",
    "hevc": "libx265",
    "mpeg4": "mpeg4",
    "mpeg2video": "mpeg2video",
    "vp9": "libvpx-vp9",
    "av1": "libaom-av1",
    "theora": "libtheora",
    "prores": "prores_ks",
    "h263": "h263",
}

def run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def run_live_capture(cmd):
    """
    Run a command (ffmpeg) and:
      - stream stdout/stderr live to the user's terminal
      - capture both into strings for later use
    Returns (returncode, captured_stdout, captured_stderr).
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    out_lines, err_lines = [], []

    def pump(src, sink, store):
        for line in src:
            sink.write(line)
            sink.flush()
            store.append(line)

    t_out = threading.Thread(target=pump, args=(proc.stdout, sys.stdout, out_lines), daemon=True)
    t_err = threading.Thread(target=pump, args=(proc.stderr, sys.stderr, err_lines), daemon=True)
    t_out.start(); t_err.start()

    rc = proc.wait()
    t_out.join(); t_err.join()

    return rc, "".join(out_lines), "".join(err_lines)

def ffprobe_json(path):
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path)
    ]
    rc, out, err = run(cmd)
    if rc != 0:
        raise RuntimeError(f"ffprobe failed for {path}:\n{err}")
    return json.loads(out)

def get_video_stream(info):
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            return s
    return None

def parse_int(x, default=None):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default

def even(n):
    # Ensure the number is even (encoders often require mod2 dimensions)
    return int(n) - (int(n) % 2)

def centered_4x3_crop(iw, ih):
    """Return (crop_w, crop_h, x, y) for a centered 4:3 crop."""
    target_w = min(iw, int(round(ih * 4 / 3)))
    target_w = even(target_w)
    target_h = even(ih)
    x = even((iw - target_w) // 2)
    y = even((ih - target_h) // 2)  # usually 0, but keep centered for safety
    return target_w, target_h, x, y

def run_cropdetect(path, seconds=15):
    """
    Run a short cropdetect scan and return the *mode* crop (w,h,x,y) if found.
    We bias toward a 4:3 width if it's very close.
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-ss", "0", "-t", str(seconds),
        "-i", str(path),
        "-vf", "cropdetect=24:16:0",
        "-f", "null", "-"
    ]
    rc, out, err = run(cmd)
    # cropdetect prints to stderr
    lines = (out + "\n" + err).splitlines()
    crops = []
    for ln in lines:
        # look for 'crop=w:h:x:y'
        if "crop=" in ln:
            try:
                frag = ln.split("crop=")[1].split()[0]
                w, h, x, y = frag.split(":")
                crops.append((int(w), int(h), int(x), int(y)))
            except Exception:
                pass
    if not crops:
        return None

    # Pick the most frequent crop suggestion
    mode = Counter(crops).most_common(1)[0][0]
    w, h, x, y = mode
    # Ensure even numbers
    return even(w), even(h), even(x), even(y)

def choose_encoder(codec_name):
    enc = CODEC_MAP.get(codec_name)
    if enc is None:
        # Fallback: try to use the same name (may work for some codecs)
        return codec_name
    return enc

def output_path_for(input_path, outdir):
    p = Path(input_path)
    stem = p.stem
    # Add tag to make it obvious it’s cropped
    return Path(outdir or p.parent, f"{stem}.4x3{p.suffix}")

def build_ffmpeg_cmd(
    src, dst, crop, v_encoder, v_bitrate=None, crf=None, preset="medium"
):
    crop_w, crop_h, x, y = crop
    vf = f"crop={crop_w}:{crop_h}:{x}:{y}"

    # Base mapping: map EVERYTHING from input (all streams)
    # - Copy non-video streams as-is
    cmd = [
        "ffmpeg", 
        "-stats", "-loglevel", "level+info",  # progress + detailed info
        "-y", "-i", str(src),
        "-map", "0",
        "-map_metadata", "0",
        "-map_chapters", "0",
        "-c:a", "copy",
        "-c:s", "copy",
        "-c:d", "copy",
        "-c:t", "copy",   # attachments where applicable (mkv)
        "-c:v", v_encoder,
        "-vf", vf,
        "-preset", preset,
    ]

    # Choose quality mode:
    if crf is not None:
        # CRF mode (constant quality)
        cmd += ["-crf", str(crf)]
        # For VP9/AV1 we should supply -b:v 0 for "constant quality"
        if v_encoder in ("libvpx-vp9", "libaom-av1"):
            cmd += ["-b:v", "0"]
    elif v_bitrate is not None and v_bitrate > 0:
        # Bitrate-based (approx. “same quality” as source)
        # Give encoder some headroom
        cmd += ["-b:v", str(v_bitrate), "-maxrate", str(v_bitrate), "-bufsize", str(int(v_bitrate)*2)]
    else:
        # No bitrate found and no CRF requested — fall back to a sensible CRF
        fallback_crf = "18" if v_encoder in ("libx264", "libx265") else "28"
        cmd += ["-crf", fallback_crf]
        if v_encoder in ("libvpx-vp9", "libaom-av1"):
            cmd += ["-b:v", "0"]

    # Preserve container metadata tags behavior and faststart for mp4/mov
    cmd += ["-movflags", "use_metadata_tags+faststart", str(dst)]
    return cmd

def main():
    ap = argparse.ArgumentParser(description="Crop pillarboxed 16:9 to true 4:3 with stream copies.")
    ap.add_argument("inputs", nargs="+", help="Input video file(s)")
    ap.add_argument("-o", "--output", help="Output directory")
    ap.add_argument("--use-cropdetect", action="store_true", help="Use ffmpeg cropdetect to find exact crop")
    ap.add_argument("--scan-seconds", type=int, default=15, help="Seconds to scan for cropdetect (default 15)")
    ap.add_argument("--crf", type=int, help="Use CRF mode instead of bitrate parity (e.g. 18).")
    ap.add_argument("--preset", default="medium", help="ffmpeg encoder preset (default: medium)")
    ap.add_argument("--dry-run", action="store_true", help="Print commands without running")
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("Error: ffmpeg/ffprobe not found in PATH.", file=sys.stderr)
        sys.exit(1)

    outdir = args.output
    if outdir:
        Path(outdir).mkdir(parents=True, exist_ok=True)

    for src in args.inputs:
        srcp = Path(src)
        if not srcp.exists():
            print(f"!! Skipping missing file: {src}", file=sys.stderr)
            continue

        info = ffprobe_json(srcp)
        v = get_video_stream(info)
        if v is None:
            print(f"!! No video stream in: {src}", file=sys.stderr)
            continue

        iw = parse_int(v.get("width"))
        ih = parse_int(v.get("height"))
        codec_name = v.get("codec_name")
        # Prefer stream-level bitrate; fall back to container if needed
        v_bitrate = parse_int(v.get("bit_rate"))
        if v_bitrate is None:
            v_bitrate = parse_int(info.get("format", {}).get("bit_rate"))
        # A touch of safety: clamp absurdly low/zero bitrates
        if v_bitrate is not None and v_bitrate < 100_000:
            v_bitrate = None

        if iw is None or ih is None:
            print(f"!! Could not read dimensions for: {src}", file=sys.stderr)
            continue

        src_aspect = iw / ih if ih else 0.0

        # Decide crop
        crop = None
        if args.use_cropdetect:
            c = run_cropdetect(srcp, seconds=args.scan_seconds)
            if c:
                cw, ch, cx, cy = c
                # if crop is extremely close to 4:3, nudge width to exact 4:3 for clean result
                if abs((cw / ch) - (4/3)) < 0.01:
                    cw = even(int(round(ch * 4 / 3)))
                    cx = even((iw - cw) // 2)
                crop = (cw, ch, cx, cy)

        if crop is None:
            # Fallback: centered 4:3 if the input is wider than 4:3 (pillarboxed)
            if src_aspect > (4/3) + 0.005:
                crop = centered_4x3_crop(iw, ih)
            else:
                print(f":: {src} already ~4:3 (aspect {src_aspect:.3f}); copying without video re-encode.")
                dst = output_path_for(srcp, outdir)
                # Just stream copy everything if no crop needed
                cmd = [
                    "ffmpeg", "-stats", "-loglevel", "level+info", "-y", "-i", str(srcp),
                    "-map", "0", "-map_metadata", "0", "-map_chapters", "0",
                    "-c", "copy", "-movflags", "use_metadata_tags+faststart",
                    str(dst)
                ]
                print("$", " ".join(shlex.quote(x) for x in cmd))
                if not args.dry_run:
                    rc, out, err = run_live_capture(cmd)
                    if rc != 0:
                        print(err, file=sys.stderr)
                        sys.exit(rc)
                continue

        # Choose encoder based on source codec
        v_encoder = choose_encoder(codec_name or "")
        if v_encoder in ("libx264", "libx265") and v.get("pix_fmt", "").endswith("10le"):
            print(f"!! Note: Input appears 10-bit ({v.get('pix_fmt')}). "
                  f"Your distro's {v_encoder} may be 8-bit only; ffmpeg could downconvert.",
                  file=sys.stderr)

        dst = output_path_for(srcp, outdir)
        cmd = build_ffmpeg_cmd(
            src=srcp,
            dst=dst,
            crop=crop,
            v_encoder=v_encoder,
            v_bitrate=v_bitrate if args.crf is None else None,
            crf=args.crf,
            preset=args.preset,
        )

        print("$", " ".join(shlex.quote(x) for x in cmd))
        if not args.dry_run:
            rc, out, err = run_live_capture(cmd)
            if rc != 0:
                print(err, file=sys.stderr)
                sys.exit(rc)

if __name__ == "__main__":
    main()

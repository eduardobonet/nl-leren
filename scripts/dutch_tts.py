#!/usr/bin/env python3
"""Generate spoken Dutch audio for tutoring replies and shadowing practice.

Uses neural Dutch voices via edge-tts (nl-NL-FennaNeural / nl-NL-MaartenNeural /
nl-NL-ColetteNeural) when available and online, with automatic offline fallback
to macOS built-in Dutch voice (Xander / Ellen via `say` + `afconvert`).
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TUTOR_AUDIO_DIR = ROOT_DIR / "road_to_B1" / "audio" / "tutor"

NEURAL_VOICES = {
    "fenna": "nl-NL-FennaNeural",
    "maarten": "nl-NL-MaartenNeural",
    "colette": "nl-NL-ColetteNeural",
    "dena": "nl-BE-DenaNeural",
    "arnaud": "nl-BE-ArnaudNeural",
}

MACOS_VOICES = {
    "xander": "Xander",
    "ellen": "Ellen",
}


def find_edge_tts_bin() -> str | None:
    venv_bin = ROOT_DIR / ".venv" / "bin" / "edge-tts"
    if venv_bin.exists():
        return str(venv_bin)
    return shutil.which("edge-tts")


def default_output_path(ext: str) -> Path:
    TUTOR_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return TUTOR_AUDIO_DIR / f"tutor_{stamp}.{ext}"


def synth_edge_tts(text: str, voice_id: str, rate: str, out_path: Path) -> bool:
    edge_bin = find_edge_tts_bin()
    if not edge_bin:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        edge_bin,
        "--voice",
        voice_id,
        f"--rate={rate}",
        "--text",
        text,
        "--write-media",
        str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
        return True
    if res.stderr:
        print(f"edge-tts failed ({res.stderr.strip().splitlines()[-1]}), falling back to macOS say.", file=sys.stderr)
    return False


def synth_macos_say(text: str, mac_voice: str, rate_wpm: int, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".mp3":
        out_path = out_path.with_suffix(".m4a")

    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
        aiff_path = Path(tmp.name)

    try:
        subprocess.run(
            ["say", "-v", mac_voice, "-r", str(rate_wpm), "-o", str(aiff_path), text],
            check=True,
        )
        subprocess.run(
            ["afconvert", "-f", "m4af", "-d", "aac", str(aiff_path), str(out_path)],
            check=True,
        )
    finally:
        if aiff_path.exists():
            aiff_path.unlink()
    return out_path


def play_audio(path: Path) -> None:
    if shutil.which("afplay"):
        subprocess.run(["afplay", str(path)], check=True)
    else:
        print(f"afplay not available; saved audio to {path}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize spoken Dutch audio (neural edge-tts + macOS fallback).")
    parser.add_argument("text", nargs="?", help="Dutch text to speak (or pass --file)")
    parser.add_argument("--file", help="Read Dutch text from a UTF-8 text file")
    parser.add_argument(
        "--voice",
        default="fenna",
        help="Voice preset: fenna (default), maarten, colette, dena, arnaud, xander, ellen",
    )
    parser.add_argument(
        "--rate",
        default="-8%",
        help="Speaking rate for edge-tts (default: -8%% for clear learner pace; use +0%% for natural speed)",
    )
    parser.add_argument(
        "--macos-wpm",
        type=int,
        default=165,
        help="Words per minute when falling back to macOS say (default: 165)",
    )
    parser.add_argument("--out", help="Output audio path (default: road_to_B1/audio/tutor/tutor_<timestamp>.mp3)")
    parser.add_argument("--play", action="store_true", help="Play the audio immediately via afplay")
    parser.add_argument("--list-voices", action="store_true", help="Show available voice presets")
    args = parser.parse_args()

    if args.list_voices:
        print("Neural voices (edge-tts):")
        for k, v in NEURAL_VOICES.items():
            print(f"  {k:10s} -> {v}")
        print("\nOffline macOS fallback voices:")
        for k, v in MACOS_VOICES.items():
            print(f"  {k:10s} -> {v}")
        print(f"\nedge-tts binary detected: {find_edge_tts_bin() or 'No (will use macOS say)'}")
        return 0

    text = Path(args.file).read_text(encoding="utf-8").strip() if args.file else (args.text or "").strip()
    if not text:
        parser.error("Provide Dutch text as an argument or via --file.")

    voice_key = args.voice.lower()
    if voice_key in MACOS_VOICES:
        out_path = Path(args.out) if args.out else default_output_path("m4a")
        final_path = synth_macos_say(text, MACOS_VOICES[voice_key], args.macos_wpm, out_path)
        backend = f"macOS say ({MACOS_VOICES[voice_key]})"
    else:
        neural_id = NEURAL_VOICES.get(voice_key, args.voice)
        out_path = Path(args.out) if args.out else default_output_path("mp3")
        if synth_edge_tts(text, neural_id, args.rate, out_path):
            final_path = out_path
            backend = f"edge-tts ({neural_id}, rate={args.rate})"
        else:
            fallback_voice = "Ellen" if voice_key in {"dena", "arnaud"} else "Xander"
            final_path = synth_macos_say(text, fallback_voice, args.macos_wpm, out_path)
            backend = f"macOS say fallback ({fallback_voice})"

    rel = final_path.relative_to(ROOT_DIR) if final_path.is_relative_to(ROOT_DIR) else final_path
    print(f"Saved: {rel} [{backend}]")
    if args.play:
        play_audio(final_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

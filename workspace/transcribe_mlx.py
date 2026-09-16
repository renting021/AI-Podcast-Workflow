#!/usr/bin/env python3
"""Transcribe podcast audio with MLX Whisper and save reusable artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlx_whisper


def timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def transcribe(audio_path: Path, output_dir: Path, model: str, language: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model,
        language=language,
        word_timestamps=True,
        condition_on_previous_text=False,
        verbose=False,
    )

    stem = audio_path.stem
    raw_path = output_dir / f"{stem}.json"
    jsonl_path = output_dir / f"{stem}.segments.jsonl"
    text_path = output_dir / f"{stem}.txt"

    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    segments = result.get("segments", [])
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments):
            record = {
                "index": index,
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": str(segment.get("text", "")).strip(),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    lines = [
        f"[{timestamp(float(segment.get('start', 0.0)))} --> "
        f"{timestamp(float(segment.get('end', 0.0)))}] "
        f"{str(segment.get('text', '')).strip()}"
        for segment in segments
        if str(segment.get("text", "")).strip()
    ]
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"completed: {audio_path.name} -> {raw_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="mlx-community/whisper-turbo")
    parser.add_argument("--language", default="zh")
    args = parser.parse_args()

    for audio_path in args.audio:
        transcribe(audio_path.resolve(), args.output_dir.resolve(), args.model, args.language)


if __name__ == "__main__":
    main()

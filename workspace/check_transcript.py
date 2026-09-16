#!/usr/bin/env python3
"""Run deterministic integrity checks on a Whisper podcast transcript."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SUSPICIOUS_TAIL_PATTERNS = (
    "明镜与点点栏目",
    "感谢观看",
    "字幕由",
    "字幕志愿者",
)


def normalized(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.transcript.read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    empty_segments = []
    non_monotonic = []
    long_gaps = []
    repeat_runs = []
    suspicious_tail = []

    previous_end = 0.0
    previous_norm = ""
    repeat_start = None
    repeat_count = 0

    for index, segment in enumerate(segments):
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", 0.0))
        text = str(segment.get("text", "")).strip()
        norm = normalized(text)

        if not text:
            empty_segments.append(index)
        if start < previous_end - 0.05 or end < start:
            non_monotonic.append(index)
        if start - previous_end >= 5.0:
            long_gaps.append({"after_index": index - 1, "start": previous_end, "end": start})
        if start >= args.duration - 45 and any(p in text for p in SUSPICIOUS_TAIL_PATTERNS):
            suspicious_tail.append({"index": index, "start": start, "end": end, "text": text})

        if norm and norm == previous_norm:
            if repeat_count == 1:
                repeat_start = index - 1
            repeat_count += 1
        else:
            if repeat_count >= 3:
                repeat_runs.append(
                    {"start_index": repeat_start, "end_index": index - 1, "count": repeat_count}
                )
            repeat_start = None
            repeat_count = 1
        previous_norm = norm
        previous_end = max(previous_end, end)

    if repeat_count >= 3:
        repeat_runs.append(
            {"start_index": repeat_start, "end_index": len(segments) - 1, "count": repeat_count}
        )

    meaningful = [
        segment
        for index, segment in enumerate(segments)
        if index not in {item["index"] for item in suspicious_tail}
    ]
    meaningful_end = float(meaningful[-1].get("end", 0.0)) if meaningful else 0.0
    coverage_ratio = meaningful_end / args.duration if args.duration else 0.0

    failures = []
    if non_monotonic:
        failures.append("non_monotonic_timestamps")
    if repeat_runs:
        failures.append("consecutive_repetition_loop")
    if coverage_ratio < 0.98:
        failures.append("coverage_below_98_percent")

    report = {
        "schema_version": 1,
        "status": "fail" if failures else "pass_with_exclusions" if suspicious_tail else "pass",
        "duration_seconds": args.duration,
        "segment_count": len(segments),
        "first_segment_start": float(segments[0].get("start", 0.0)) if segments else None,
        "last_segment_end": float(segments[-1].get("end", 0.0)) if segments else None,
        "meaningful_end": meaningful_end,
        "coverage_ratio": round(coverage_ratio, 4),
        "empty_segments": empty_segments,
        "non_monotonic_segments": non_monotonic,
        "long_gaps": long_gaps,
        "repeat_runs": repeat_runs,
        "excluded_suspicious_tail": suspicious_tail,
        "failures": failures,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: segments={len(segments)} coverage={coverage_ratio:.2%}")


if __name__ == "__main__":
    main()

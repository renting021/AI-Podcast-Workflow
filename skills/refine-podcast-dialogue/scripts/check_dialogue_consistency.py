#!/usr/bin/env python3
"""Detect dialogue-to-narrative style drift in interview Markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
LABEL_RE = re.compile(r"^\s*(?:[-*]\s*)?\*\*([^*\n：:]{1,24})[：:]\*\*", re.MULTILINE)
NARRATIVE_RE = re.compile(
    r"(?:主持人|主播)(?:问|追问|提到|表示|总结|注意到|确认|据此)"
    r"|(?:嘉宾|Simon|Beibin|杜少雷|李辈滨)(?:表示|解释|认为|补充|指出|介绍|回答|确认|提到)"
    r"|节目(?:讨论|随后|最后|把|以|中|给出|没有)"
)
EXEMPT_RE = re.compile(
    r"摘要|嘉宾介绍|阅读提示|来源|关键观点|文本说明|编辑说明|节目信息|完整讨论留下|置信度"
)
NON_SPEAKER_LABELS = {
    "时间范围",
    "核心结论",
    "说明",
    "提示",
    "来源",
    "问题",
    "回答",
}


@dataclass
class SectionMetric:
    heading: str
    line: int
    characters: int
    dialogue_labels: int
    narrative_signals: int
    dialogue_density_per_1000: float
    dialogue_signal_share: float
    exempt: bool
    failures: list[str]


def nonspace_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def dialogue_labels(text: str) -> list[str]:
    labels = []
    for match in LABEL_RE.finditer(text):
        label = match.group(1).strip()
        if label not in NON_SPEAKER_LABELS:
            labels.append(label)
    return labels


def split_sections(text: str) -> list[tuple[str, int, str]]:
    matches = list(HEADING_RE.finditer(text))
    sections: list[tuple[str, int, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        line = text.count("\n", 0, match.start()) + 1
        sections.append((match.group(1).strip(), line, text[start:end]))
    return sections


def analyze(args: argparse.Namespace) -> dict:
    path = Path(args.article).expanduser().resolve()
    text = path.read_text(encoding="utf-8")
    sections = split_sections(text)
    metrics: list[SectionMetric] = []

    for heading, line, body in sections:
        chars = nonspace_chars(body)
        labels = len(dialogue_labels(body))
        narratives = len(NARRATIVE_RE.findall(body))
        density = (labels * 1000 / chars) if chars else 0.0
        signals = labels + narratives
        share = (labels / signals) if signals else 1.0
        exempt = bool(EXEMPT_RE.search(heading))
        failures: list[str] = []

        if not exempt and chars >= args.min_section_chars:
            if labels == 0 and narratives > 0:
                failures.append("no_dialogue_labels_with_narrative_attribution")
            if narratives > 0 and density < args.min_dialogue_density:
                failures.append("dialogue_density_below_threshold")

        metrics.append(
            SectionMetric(
                heading=heading,
                line=line,
                characters=chars,
                dialogue_labels=labels,
                narrative_signals=narratives,
                dialogue_density_per_1000=round(density, 3),
                dialogue_signal_share=round(share, 3),
                exempt=exempt,
                failures=failures,
            )
        )

    active = [metric for metric in metrics if not metric.exempt]
    total_labels = sum(metric.dialogue_labels for metric in active)
    total_narratives = sum(metric.narrative_signals for metric in active)
    total_signals = total_labels + total_narratives
    global_share = total_labels / total_signals if total_signals else 0.0

    drift_boundaries: list[dict] = []
    for previous, current in zip(active, active[1:]):
        if (
            previous.dialogue_density_per_1000 >= args.min_dialogue_density
            and current.dialogue_density_per_1000 < args.min_dialogue_density / 4
            and current.narrative_signals > 0
        ):
            current.failures.append("abrupt_cross_section_style_drift")
            drift_boundaries.append(
                {
                    "from": previous.heading,
                    "to": current.heading,
                    "line": current.line,
                }
            )

    failing = [metric for metric in active if metric.failures]
    global_failures: list[str] = []
    if total_signals and global_share < args.min_global_dialogue_share:
        global_failures.append("global_dialogue_signal_share_below_threshold")
    if not sections:
        global_failures.append("no_level_two_sections_found")

    status = "fail" if failing or global_failures else "pass"
    return {
        "schema_version": 1,
        "article": str(path),
        "status": status,
        "thresholds": {
            "min_section_chars": args.min_section_chars,
            "min_dialogue_density_per_1000": args.min_dialogue_density,
            "min_global_dialogue_signal_share": args.min_global_dialogue_share,
        },
        "summary": {
            "sections": len(metrics),
            "active_sections": len(active),
            "failing_sections": len(failing),
            "dialogue_labels": total_labels,
            "narrative_signals": total_narratives,
            "global_dialogue_signal_share": round(global_share, 3),
        },
        "global_failures": global_failures,
        "drift_boundaries": drift_boundaries,
        "sections": [asdict(metric) for metric in metrics],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect dialogue style loss and cross-section drift in interview Markdown."
    )
    parser.add_argument("article", help="Markdown article to inspect")
    parser.add_argument("--json-out", help="Write the full report to this path")
    parser.add_argument("--min-section-chars", type=int, default=180)
    parser.add_argument("--min-dialogue-density", type=float, default=0.45)
    parser.add_argument("--min-global-dialogue-share", type=float, default=0.55)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = analyze(args)
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json_out:
        output = Path(args.json_out).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        f"{report['status'].upper()}: sections={summary['active_sections']} "
        f"failing={summary['failing_sections']} labels={summary['dialogue_labels']} "
        f"narrative={summary['narrative_signals']} share={summary['global_dialogue_signal_share']}"
    )
    for boundary in report["drift_boundaries"]:
        print(
            f"DRIFT line {boundary['line']}: {boundary['from']} -> {boundary['to']}",
            file=sys.stderr,
        )
    for section in report["sections"]:
        if section["failures"]:
            print(
                f"FAIL line {section['line']} {section['heading']}: "
                + ", ".join(section["failures"]),
                file=sys.stderr,
            )
    for failure in report["global_failures"]:
        print(f"FAIL global: {failure}", file=sys.stderr)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

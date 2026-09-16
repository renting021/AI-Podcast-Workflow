#!/usr/bin/env python3
"""Merge podcast front matter and ordered article parts without altering content."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--output", default="article_draft.md")
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    inputs = [project_dir / "article_frontmatter.md", *sorted(project_dir.glob("article_part_*.md"))]
    footer = project_dir / "article_footer.md"
    if footer.exists():
        inputs.append(footer)
    missing = [str(path) for path in inputs if not path.exists()]
    if missing:
        raise SystemExit("missing inputs: " + ", ".join(missing))

    content = "\n\n".join(path.read_text(encoding="utf-8").strip() for path in inputs) + "\n"
    output = project_dir / args.output
    output.write_text(content, encoding="utf-8")
    print(f"merged {len(inputs)} files -> {output}")


if __name__ == "__main__":
    main()

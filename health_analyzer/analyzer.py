"""Count source files and lines and produce repository health reports."""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

if __package__:
    from .report import generate_markdown_report
else:
    from report import generate_markdown_report

LANGUAGES = {
    ".py": "Python",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
}

IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules",
    "__pycache__", "build", "dist", ".pytest_cache",
}


def analyze_repository(root: Path, large_file_threshold=500):
    if large_file_threshold < 0:
        raise ValueError("large_file_threshold must be non-negative")

    root = root.resolve()

    if not root.is_dir():
        raise ValueError(f"Repository directory not found: {root}")

    languages = Counter()
    large_files = []
    total_files = 0
    total_lines = 0

    for directory, directories, filenames in os.walk(root):
        directory_path = Path(directory)
        directories[:] = [
            name for name in directories
            if name not in IGNORED_DIRS
            and not (directory_path / name).is_symlink()
        ]

        for filename in filenames:
            path = directory_path / filename
            language = LANGUAGES.get(path.suffix.lower())
            if not language or path.is_symlink() or not path.is_file():
                continue

            try:
                with path.open("r", encoding="utf-8") as file:
                    line_count = sum(1 for _ in file)
            except (UnicodeError, OSError):
                continue

            total_files += 1
            total_lines += line_count
            languages[language] += 1

            if line_count > large_file_threshold:
                large_files.append({
                    "path": path.relative_to(root).as_posix(),
                    "lines": line_count,
                })

    return {
        "repository": root.name,
        "total_files": total_files,
        "total_lines": total_lines,
        "languages": dict(sorted(languages.items())),
        "large_files": sorted(
            large_files,
            key=lambda item: (-item["lines"], item["path"]),
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze repository health metrics"
    )
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--threshold", type=int, default=500)
    parser.add_argument("--output", default="health-report.json")
    parser.add_argument(
        "--markdown-output",
        help="also save a Markdown report to this path",
    )
    args = parser.parse_args()

    if args.threshold < 0:
        parser.error("--threshold must be non-negative")

    output = Path(args.output)
    markdown_output = Path(args.markdown_output) if args.markdown_output else None
    if markdown_output and markdown_output.resolve() == output.resolve():
        parser.error("JSON and Markdown output paths must be different")

    try:
        report = analyze_repository(Path(args.path), args.threshold)
        output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if markdown_output:
            generate_markdown_report(report, markdown_output)
    except (ValueError, OSError) as error:
        parser.error(str(error))

    print(f"Analyzed {report['total_files']} files")
    print(f"Total lines: {report['total_lines']}")
    print(f"Report saved: {output}")
    if markdown_output:
        print(f"Markdown report saved: {markdown_output}")


if __name__ == "__main__":
    main()

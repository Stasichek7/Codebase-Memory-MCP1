
"""Render repository metrics as a Markdown report."""

from pathlib import Path


def generate_markdown_report(report: dict, output_path: str = "health-report.md"):
    """Generate a Markdown report from repository metrics."""

    lines = [
        "# Repository Health Report",
        "",
        f"**Repository:** {report['repository']}",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total files | {report['total_files']} |",
        f"| Total lines | {report['total_lines']} |",
        f"| Large files | {len(report['large_files'])} |",
        "",
        "## Programming Languages",
        "",
        "| Language | Files |",
        "|---|---:|",
    ]

    for language, count in sorted(report["languages"].items()):
        lines.append(f"| {language} | {count} |")

    lines.extend([
        "",
        "## Large Files",
        "",
    ])

    if report["large_files"]:
        lines.extend([
            "| File | Lines |",
            "|---|---:|",
        ])

        for file in report["large_files"]:
            path = file["path"].replace("|", "\\|")
            lines.append(f"| `{path}` | {file['lines']} |")
    else:
        lines.append("No large files detected.")

    lines.extend([
        "",
        "## Recommendations",
        "",
    ])

    if report["large_files"]:
        lines.append(
            "- Review large files and consider splitting "
            "them into smaller modules."
        )
    else:
        lines.append(
            "- No files exceed the configured size threshold."
        )

    lines.append(
        "- Review code quality with automated tests and linters."
    )

    content = "\n".join(lines) + "\n"

    Path(output_path).write_text(content, encoding="utf-8")

    return content

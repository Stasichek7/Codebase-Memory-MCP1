import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from health_analyzer.analyzer import analyze_repository
from health_analyzer.report import generate_markdown_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class HealthAnalyzerTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name)

    def write_source(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, *arguments):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(PROJECT_ROOT), environment.get("PYTHONPATH")])
        )
        return subprocess.run(
            [sys.executable, "-m", "health_analyzer.analyzer", *arguments],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    def test_counts_supported_sources_and_strict_large_file_threshold(self):
        self.write_source("app.py", "first\nsecond\n")
        self.write_source("nested/view.TSX", "first\nsecond\nthird")
        self.write_source("empty.c", "")
        self.write_source("README.md", "Documentation is not source.\n")

        report = analyze_repository(self.root, large_file_threshold=2)

        self.assertEqual(report["repository"], self.root.name)
        self.assertEqual(report["total_files"], 3)
        self.assertEqual(report["total_lines"], 5)
        self.assertEqual(
            report["languages"], {"C": 1, "Python": 1, "TypeScript": 1}
        )
        self.assertEqual(
            report["large_files"], [{"path": "nested/view.TSX", "lines": 3}]
        )

    def test_ignores_generated_directories_and_invalid_utf8(self):
        self.write_source("src/main.py", "print('hello')\n")
        for directory in [".git", "node_modules", "build", "nested/.venv"]:
            self.write_source(directory + "/ignored.py", "ignored\n" * 10)
        (self.root / "invalid.py").write_bytes(b"\xff\xfe\x00")

        report = analyze_repository(self.root)

        self.assertEqual(report["total_files"], 1)
        self.assertEqual(report["total_lines"], 1)
        self.assertEqual(report["languages"], {"Python": 1})

    def test_empty_repository_returns_zero_metrics(self):
        report = analyze_repository(self.root)

        self.assertEqual(report["total_files"], 0)
        self.assertEqual(report["total_lines"], 0)
        self.assertEqual(report["languages"], {})
        self.assertEqual(report["large_files"], [])

    def test_rejects_missing_root_and_negative_threshold(self):
        with self.assertRaises(ValueError):
            analyze_repository(self.root / "missing")
        regular_file = self.write_source("app.py", "pass\n")
        with self.assertRaises(ValueError):
            analyze_repository(regular_file)
        with self.assertRaises(ValueError):
            analyze_repository(self.root, large_file_threshold=-1)

    def test_large_file_order_is_stable_for_equal_sizes(self):
        self.write_source("z.py", "line\n" * 3)
        self.write_source("nested/a.c", "line\n" * 4)
        self.write_source("a.py", "line\n" * 3)

        report = analyze_repository(self.root, large_file_threshold=0)

        self.assertEqual(
            [entry["path"] for entry in report["large_files"]],
            ["nested/a.c", "a.py", "z.py"],
        )
        self.assertEqual(report, analyze_repository(self.root, 0))

    def test_skips_file_and_directory_symlinks(self):
        source = self.write_source("real/app.py", "pass\n")
        try:
            (self.root / "linked.py").symlink_to(source)
            (self.root / "linked_directory").symlink_to(
                source.parent, target_is_directory=True
            )
        except (OSError, NotImplementedError) as error:
            self.skipTest("Symlink creation is unavailable: {}".format(error))

        report = analyze_repository(self.root)

        self.assertEqual(report["total_files"], 1)
        self.assertEqual(report["total_lines"], 1)

    def test_markdown_report_writes_readable_metrics_and_escaped_paths(self):
        report = {
            "repository": "example",
            "total_files": 2,
            "total_lines": 42,
            "languages": {"Python": 1, "C": 1},
            "large_files": [{"path": "src/a|b.py", "lines": 40}],
        }
        output = self.root / "report.md"

        content = generate_markdown_report(report, output)

        self.assertEqual(output.read_text(encoding="utf-8"), content)
        self.assertIn("# Repository Health Report", content)
        self.assertIn("| Total files | 2 |", content)
        self.assertIn("| Total lines | 42 |", content)
        self.assertIn("| `src/a\\|b.py` | 40 |", content)
        self.assertLess(content.index("| C | 1 |"), content.index("| Python | 1 |"))

    def test_markdown_report_handles_no_large_files(self):
        report = analyze_repository(self.root)

        content = generate_markdown_report(report, self.root / "empty.md")

        self.assertIn("No large files detected.", content)
        self.assertIn("No files exceed the configured size threshold.", content)

    def test_cli_writes_default_json_report(self):
        self.write_source("app.py", "pass\n")

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / "health-report.json").read_text("utf-8"))
        self.assertEqual(report["total_files"], 1)
        self.assertIn("Analyzed 1 files", result.stdout)

    def test_cli_writes_custom_json_and_markdown_reports(self):
        self.write_source("app.py", "first\nsecond\n")

        result = self.run_cli(
            str(self.root),
            "--threshold", "1",
            "--output", "custom.json",
            "--markdown-output", "custom.md",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / "custom.json").read_text("utf-8"))
        self.assertEqual(report["large_files"], [{"path": "app.py", "lines": 2}])
        self.assertIn("| `app.py` | 2 |", (self.root / "custom.md").read_text("utf-8"))

    def test_direct_script_runs_without_pythonpath(self):
        self.write_source("app.py", "pass\n")
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)

        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "health_analyzer" / "analyzer.py"),
                "--markdown-output", "report.md",
            ],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / "health-report.json").read_text("utf-8"))
        self.assertEqual(report["total_files"], 1)
        self.assertIn("| Python | 1 |", (self.root / "report.md").read_text("utf-8"))

    def test_cli_invalid_arguments_produce_actionable_errors(self):
        cases = [
            (("--threshold", "-1"), "--threshold must be non-negative"),
            ((str(self.root / "missing"),), "Repository directory not found"),
            (
                ("--output", "same.json", "--markdown-output", "same.json"),
                "JSON and Markdown output paths must be different",
            ),
        ]
        for arguments, message in cases:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "health-report.json").exists())


if __name__ == "__main__":
    unittest.main()

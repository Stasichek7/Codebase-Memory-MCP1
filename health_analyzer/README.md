# Repository health analyzer

Generate a local inventory of source files, line counts, and large files. The
analyzer uses the Python standard library and runs with Python 3.8 or newer.

Run commands from the repository root.

```bash
python -m health_analyzer.analyzer . --output health-report.json --markdown-output health-report.md --threshold 500
```

Replace `.` with the directory to analyze. The JSON report defaults to
`health-report.json`. Add `--markdown-output` to write a Markdown report alongside
the JSON output. Report paths are relative to the current working directory.

## Report contents

- Repository directory name.
- Total number of supported source files and their combined line count.
- Number of source files for each language.
- Relative paths and line counts of files strictly above the threshold, sorted
  by descending line count and then path.

The default threshold is 500 lines. A file with exactly 500 lines is included in
the totals and omitted from the large-file list. The threshold must be
non-negative.

## Supported files

| Language | Extensions |
|---|---|
| Python | `.py` |
| C | `.c` |
| C/C++ Header | `.h` |
| C++ | `.cpp` |
| JavaScript | `.js` |
| TypeScript | `.ts`, `.tsx` |
| Go | `.go` |
| Rust | `.rs` |
| Java | `.java` |

Extension matching is case-insensitive. Files are read as UTF-8, and unreadable
files or files containing invalid UTF-8 are skipped.

The analyzer skips symbolic links and prunes directories named `.git`, `.venv`,
`venv`, `node_modules`, `__pycache__`, `build`, `dist`, or `.pytest_cache` at any
depth. Other supported files are included, including generated or vendored code
outside those directories. The analyzer uses these directory exclusions and
does not read `.gitignore` or `.cbmignore`.

## Interpreting a report

Line counts include blank lines and comments. Large-file entries identify files
to review, and the Markdown report provides general review suggestions. These
metrics describe repository size. Assessing correctness, complexity, or test
coverage requires separate checks.

The experimental Python MCP backend has its own `repository_health` tool for
Python syntax errors and oversized Python files. Its setup and MCP capabilities
are documented in the [Python package guide](../pkg/pypi/README.md#pure-python-mcp-backend-experimental).

## Tests

```bash
python -m unittest discover -s tests -p test_health_analyzer.py -v
```

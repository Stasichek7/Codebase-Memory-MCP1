# codebase-memory-mcp

mcp-name: io.github.DeusData/codebase-memory-mcp

**Fast code intelligence engine for AI coding agents.** Indexes an average repository in milliseconds, the Linux kernel (28M LOC) in 3 minutes. Answers structural queries in under 1ms.

This Python wrapper downloads the selected `codebase-memory-mcp` runtime set from [GitHub Releases](https://github.com/DeusData/codebase-memory-mcp/releases) on first run and verifies it before publishing it in your OS cache directory. The set contains the native executable and authenticated integration asset, with the graph UI always embedded.

## Installation

```bash
pip install codebase-memory-mcp
# or
pipx install codebase-memory-mcp
```

There is one composition per platform: the graph UI ships in every build, so no variant selection is needed.

For testing, `CBM_DOWNLOAD_URL` overrides the download base URL (default `https://github.com/DeusData/codebase-memory-mcp/releases/download/v<version>`): the archive and `checksums.txt` are fetched from `<CBM_DOWNLOAD_URL>/<file>`. It must be `https://`, or plain `http://` to exactly `localhost`, `127.0.0.1`, or `[::1]` (optional port; no proxy, no redirects).

## Usage

```bash
codebase-memory-mcp install   # configure your coding agents
codebase-memory-mcp --help
```

## Pure-Python MCP backend (experimental)

The package also provides an opt-in Python implementation for local Python
repositories. It uses only the Python standard library and does not download or
launch the native executable:

```bash
codebase-memory-mcp-python --root C:\path\to\your\repository
```

For VS Code, add a server entry to `.vscode/mcp.json` and change the root path:

```json
{
  "servers": {
    "codebase-memory-python": {
      "type": "stdio",
      "command": "codebase-memory-mcp-python",
      "args": ["--root", "C:\\path\\to\\your\\repository"]
    }
  }
}
```

Other MCP clients can launch the same command with the repository path as its
`--root` argument. The server communicates over newline-delimited JSON-RPC on
standard input and output. It indexes Python
modules, classes, functions, and local imports. Tools include
`search_symbols`, `search_text`, `file_outline`, `read_source`,
`dependency_impact`, `repository_health`, and `change_risk`.
`index_repository` refreshes the in-memory snapshot. Source reads are limited
to 200 lines; search results are bounded and report when more matches were
found.

`repository_health` reports syntax errors and oversized Python files.
`change_risk` adds a local-import impact estimate and test-proximity signals;
its score is heuristic and is not a replacement for running tests. The
`health_score` is also a simple heuristic, not a quality or test-coverage
measurement. This experimental backend analyzes Python source only. The existing
`codebase-memory-mcp` command and its verified native runtime remain unchanged.

## Supported platforms

| OS      | Architecture |
|---------|-------------|
| macOS   | arm64, amd64 |
| Linux   | arm64, amd64 |
| Windows | arm64, amd64 |

## Full documentation

See [github.com/DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)

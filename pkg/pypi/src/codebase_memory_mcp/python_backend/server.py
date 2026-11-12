"""Line-delimited JSON-RPC MCP server for local Python repositories."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .index import RepositoryIndex


_TOOLS = [
    {
        "name": "index_repository",
        "description": (
            "Build or refresh a local AST index of Python files in the configured "
            "repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "search_symbols",
        "description": "Find Python functions and classes by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "file_outline",
        "description": "Show definitions and local Python imports in one indexed file.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_source",
        "description": "Read up to 200 lines from an indexed Python file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_text",
        "description": "Find case-insensitive text matches in indexed Python files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "dependency_impact",
        "description": "Find files that directly or transitively import a Python file.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "repository_health",
        "description": "Summarize Python file count, symbols, large files, syntax errors, and index warnings.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "change_risk",
        "description": (
            "Estimate review risk for changed Python files using import reach, "
            "file size, and test proximity."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 100,
                }
            },
            "required": ["paths"],
            "additionalProperties": False,
        },
    },
]


class McpServer:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("Repository directory not found: {}".format(self.root))
        self._index = None

    def _get_index(self, refresh: bool = False) -> RepositoryIndex:
        if refresh or self._index is None:
            self._index = RepositoryIndex(self.root)
        return self._index

    def _call_tool(self, name: str, arguments: dict) -> dict:
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be a JSON object")
        if name == "index_repository":
            index = self._get_index(refresh=True)
            health = index.repository_health()
            return {
                "indexed_files": health["python_files"],
                "indexed_symbols": health["symbols"],
                "repository": health["repository"],
                "warnings": health["warnings"],
            }

        if name not in {
            "search_symbols",
            "file_outline",
            "read_source",
            "search_text",
            "dependency_impact",
            "repository_health",
            "change_risk",
        }:
            raise ValueError("unknown tool: {}".format(name))

        index = self._get_index()
        if name == "search_symbols":
            query = arguments.get("query")
            if not isinstance(query, str):
                raise ValueError("query must be a string")
            limit = arguments.get("limit", 20)
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise ValueError("limit must be an integer")
            return {"matches": index.search_symbols(query, limit)}
        if name == "file_outline":
            return index.file_outline(_required_string(arguments, "path"))
        if name == "read_source":
            start_line = arguments.get("start_line", 1)
            end_line = arguments.get("end_line")
            return index.read_source(
                _required_string(arguments, "path"), start_line, end_line
            )
        if name == "search_text":
            query = arguments.get("query")
            if not isinstance(query, str):
                raise ValueError("query must be a string")
            limit = arguments.get("limit", 50)
            return index.search_text(query, limit)
        if name == "dependency_impact":
            return index.dependency_impact(_required_string(arguments, "path"))
        if name == "repository_health":
            return index.repository_health()
        if name == "change_risk":
            paths = arguments.get("paths")
            if not isinstance(paths, list) or not all(
                isinstance(path, str) for path in paths
            ):
                raise ValueError("paths must be an array of strings")
            return index.change_risk(paths)

    def handle(self, request: dict) -> Optional[dict]:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return _error_response(None, -32600, "Invalid Request")
        method = request.get("method")
        request_id = request.get("id")
        if not isinstance(method, str):
            return _error_response(request_id, -32600, "Invalid Request")
        if "id" not in request:
            return None

        if method == "initialize":
            params = request.get("params")
            requested_version = (
                params.get("protocolVersion")
                if isinstance(params, dict)
                else None
            )
            supported_versions = {
                "2024-11-05",
                "2025-03-26",
                "2025-06-18",
            }
            protocol_version = (
                requested_version
                if isinstance(requested_version, str)
                and requested_version in supported_versions
                else "2025-03-26"
            )
            result = {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "codebase-memory-mcp-python",
                    "version": "0.1.0",
                },
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": _TOOLS}
        elif method == "tools/call":
            params = request.get("params")
            if not isinstance(params, dict) or not isinstance(
                params.get("name"), str
            ):
                return _error_response(request_id, -32602, "Invalid params")
            arguments = params.get("arguments", {})
            try:
                output = self._call_tool(params["name"], arguments)
            except ValueError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                }
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            output, ensure_ascii=False, separators=(",", ":")
                        ),
                    }
                ],
                "isError": False,
            }
        else:
            return _error_response(request_id, -32601, "Method not found")

        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def serve(self, input_stream=None, output_stream=None) -> None:
        input_stream = input_stream or sys.stdin
        output_stream = output_stream or sys.stdout
        for line in input_stream:
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                response = _error_response(None, -32700, "Parse error: {}".format(exc))
            else:
                response = self.handle(request)
            if response is not None:
                output_stream.write(
                    json.dumps(response, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )
                output_stream.flush()


def _required_string(arguments: dict, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(key))
    return value


def _error_response(request_id, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the pure-Python MCP backend for a Python repository."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repository root to index (default: current directory)",
    )
    args = parser.parse_args(argv)
    try:
        McpServer(Path(args.root)).serve()
    except (OSError, ValueError) as exc:
        print("codebase-memory-mcp-python: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

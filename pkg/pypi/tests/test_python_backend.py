import io
import json
import tempfile
import unittest
from pathlib import Path

from codebase_memory_mcp.python_backend.index import RepositoryIndex
from codebase_memory_mcp.python_backend.server import McpServer


class RepositoryIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "app.py").write_text(
            "from package.worker import run\n\n"
            "def main():\n"
            "    return run()\n",
            encoding="utf-8",
        )
        (self.root / "package").mkdir()
        (self.root / "package" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "package" / "helper.py").write_text(
            "def assist():\n    return None\n", encoding="utf-8"
        )
        (self.root / "package" / "worker.py").write_text(
            "from .helper import assist\n\n"
            "class Worker:\n"
            "    def execute(self):\n"
            "        return None\n\n"
            "def run():\n"
            "    return Worker().execute()\n",
            encoding="utf-8",
        )
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_app.py").write_text(
            "from app import main\n\n"
            "def test_main():\n"
            "    main()\n",
            encoding="utf-8",
        )
        (self.root / "broken.py").write_text("def unfinished(:\n", encoding="utf-8")
        (self.root / ".venv").mkdir()
        (self.root / ".venv" / "ignored.py").write_text(
            "def ignored(): pass\n", encoding="utf-8"
        )
        self.index = RepositoryIndex(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_indexes_symbols_and_local_imports(self):
        matches = self.index.search_symbols("execute")
        self.assertEqual(matches[0]["qualified_name"], "Worker.execute")
        self.assertEqual(self.index.files["app.py"].imports, {"package/worker.py"})
        self.assertEqual(
            self.index.files["package/worker.py"].imports, {"package/helper.py"}
        )
        self.assertEqual(
            self.index.dependency_impact("package/worker.py")[
                "transitive_dependents"
            ],
            ["app.py", "tests/test_app.py"],
        )

    def test_health_and_change_risk_include_unique_repository_signals(self):
        health = self.index.repository_health()
        self.assertEqual(health["python_files"], 6)
        self.assertEqual(health["syntax_errors"][0]["path"], "broken.py")

        risk = self.index.change_risk(["package/worker.py"])
        self.assertEqual(
            risk["impacted_files"], ["app.py", "tests/test_app.py"]
        )
        self.assertEqual(risk["impacted_tests"], ["tests/test_app.py"])
        self.assertEqual(risk["risk_level"], "low")

    def test_rejects_paths_outside_repository_and_invalid_search(self):
        with self.assertRaises(ValueError):
            self.index.file_outline("../outside.py")
        with self.assertRaises(ValueError):
            self.index.search_symbols(" ")
        with self.assertRaises(ValueError):
            self.index.change_risk([])

    def test_reads_bounded_source_ranges_and_searches_text(self):
        source = self.index.read_source("package/worker.py", 1, 2)
        self.assertEqual(source["content"], "from .helper import assist\n")
        self.assertEqual(source["start_line"], 1)
        matches = self.index.search_text("ASSIST")
        self.assertEqual(matches["matches"][0]["path"], "package/helper.py")
        self.assertFalse(matches["truncated"])

    def test_source_tools_reject_invalid_ranges_and_limits(self):
        with self.assertRaises(ValueError):
            self.index.read_source("app.py", 0)
        with self.assertRaises(ValueError):
            self.index.read_source("app.py", 1, 201)
        with self.assertRaises(ValueError):
            self.index.search_text("main", 101)

    def test_architecture_map_reports_import_cycles_and_bounded_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alpha.py").write_text(
                "import beta\n", encoding="utf-8"
            )
            (root / "beta.py").write_text(
                "import alpha\n", encoding="utf-8"
            )
            (root / "standalone.py").write_text(
                "def independent(): pass\n", encoding="utf-8"
            )
            architecture = RepositoryIndex(root).architecture_map(limit=2)

            self.assertEqual(architecture["total_modules"], 3)
            self.assertTrue(architecture["truncated"])
            self.assertEqual(
                architecture["cycles"], [["alpha.py", "beta.py"]]
            )
            self.assertEqual(architecture["total_edges"], 2)

    def test_architecture_map_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            self.index.architecture_map(limit=201)


class McpServerTests(unittest.TestCase):
    def test_initialize_and_tool_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            server = McpServer(Path(directory))
            initialized = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18"},
                }
            )
            self.assertEqual(
                initialized["result"]["protocolVersion"], "2025-06-18"
            )
            tools = server.handle(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
            )["result"]["tools"]
            self.assertIn("repository_health", [tool["name"] for tool in tools])
            self.assertIn("change_risk", [tool["name"] for tool in tools])
            self.assertIn("read_source", [tool["name"] for tool in tools])
            self.assertIn("search_text", [tool["name"] for tool in tools])
            self.assertIn("architecture_map", [tool["name"] for tool in tools])

    def test_stdio_uses_one_json_rpc_response_per_line(self):
        with tempfile.TemporaryDirectory() as directory:
            server = McpServer(Path(directory))
            incoming = io.StringIO(
                '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
                '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            )
            outgoing = io.StringIO()
            server.serve(incoming, outgoing)
            responses = [json.loads(line) for line in outgoing.getvalue().splitlines()]
            self.assertEqual(responses, [{"jsonrpc": "2.0", "id": 1, "result": {}}])

    def test_tool_errors_are_returned_as_mcp_tool_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            server = McpServer(Path(directory))
            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "file_outline",
                        "arguments": {"path": "../outside.py"},
                    },
                }
            )
            self.assertTrue(response["result"]["isError"])
            self.assertIn(
                "inside the repository root",
                response["result"]["content"][0]["text"],
            )

    def test_index_tool_refreshes_the_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.py").write_text("def first(): pass\n", encoding="utf-8")
            server = McpServer(root)
            self.assertEqual(len(server._get_index().files), 1)
            (root / "second.py").write_text("def second(): pass\n", encoding="utf-8")

            result = server._call_tool("index_repository", {})

            self.assertEqual(result["indexed_files"], 2)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path


class VsCodeMcpConfigTests(unittest.TestCase):
    def test_workspace_config_launches_python_backend_from_checkout(self):
        repository_root = Path(__file__).resolve().parents[3]
        config_path = repository_root / ".vscode" / "mcp.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        server = config["servers"]["codebase-memory-python"]

        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "python")
        self.assertEqual(
            server["args"],
            [
                "-m",
                "codebase_memory_mcp.python_backend.server",
                "--root",
                "${workspaceFolder}",
            ],
        )
        self.assertEqual(server["cwd"], "${workspaceFolder}")
        self.assertEqual(
            server["env"]["PYTHONPATH"],
            "${workspaceFolder}\\pkg\\pypi\\src",
        )


if __name__ == "__main__":
    unittest.main()

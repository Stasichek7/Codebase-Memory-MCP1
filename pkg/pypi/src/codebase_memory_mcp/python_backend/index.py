"""AST-based Python repository index and dependency analysis."""

import ast
import importlib.util
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "build",
        "dist",
    }
)
MAX_SOURCE_BYTES = 2_000_000
LARGE_FILE_LINES = 500
MAX_SOURCE_LINES = 200


@dataclass(frozen=True)
class Symbol:
    name: str
    qualified_name: str
    kind: str
    path: str
    line: int
    end_line: int


@dataclass
class FileRecord:
    path: str
    line_count: int
    import_names: Set[str] = field(default_factory=set, repr=False)
    symbols: List[Symbol] = field(default_factory=list)
    imports: Set[str] = field(default_factory=set)
    syntax_error: Optional[str] = None


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.symbols = []
        self.scope = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition(node, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition(node, "async function")

    def _visit_definition(self, node: ast.AST, kind: str) -> None:
        name = node.name
        qualified_name = ".".join(self.scope + [name])
        self.symbols.append(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=kind,
                path=self.path,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
            )
        )
        self.scope.append(name)
        self.generic_visit(node)
        self.scope.pop()


def _module_name(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _inside_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_imports(
    records: Dict[str, FileRecord], modules: Dict[str, str]
) -> None:
    for path, record in records.items():
        for name in record.import_names:
            target = modules.get(name)
            if target is None:
                components = name.split(".")
                while len(components) > 1 and target is None:
                    components.pop()
                    target = modules.get(".".join(components))
            if target and target != path:
                record.imports.add(target)


def _collect_import_names(tree: ast.AST, relative_path: Path) -> Set[str]:
    module = _module_name(relative_path)
    package = (
        module
        if relative_path.name == "__init__.py"
        else module.rpartition(".")[0]
    )
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                try:
                    imported_module = importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package
                    )
                except (ImportError, ValueError):
                    continue
            else:
                imported_module = node.module or ""
            if imported_module:
                names.add(imported_module)
                names.update(
                    imported_module + "." + alias.name for alias in node.names
                )
    return names


class RepositoryIndex:
    """A read-only snapshot of Python files, symbols, and local imports."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("Repository directory not found: {}".format(self.root))

        self.files = {}
        self.warnings = []
        self._build()

    def _build(self) -> None:
        modules = {}

        def record_walk_error(error: OSError) -> None:
            self.warnings.append(
                "{}: {}".format(error.filename or self.root, error)
            )

        for current, directories, filenames in os.walk(
            str(self.root),
            topdown=True,
            onerror=record_walk_error,
            followlinks=False,
        ):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in IGNORED_DIRS
                and not (Path(current) / directory).is_symlink()
            )
            for filename in sorted(filenames):
                candidate = Path(current) / filename
                if candidate.suffix.lower() != ".py" or candidate.is_symlink():
                    continue
                relative = candidate.relative_to(self.root)
                relative_name = relative.as_posix()
                if not _inside_root(candidate.resolve(), self.root):
                    continue

                try:
                    size = candidate.stat().st_size
                    if size > MAX_SOURCE_BYTES:
                        self.warnings.append(
                            "{}: skipped file larger than {} bytes".format(
                                relative_name, MAX_SOURCE_BYTES
                            )
                        )
                        continue
                    source_bytes = candidate.read_bytes()
                    source = source_bytes.decode("utf-8")
                except (OSError, UnicodeError) as exc:
                    self.warnings.append("{}: {}".format(relative_name, exc))
                    continue

                record = FileRecord(
                    path=relative_name, line_count=len(source.splitlines())
                )
                try:
                    tree = ast.parse(source, filename=relative_name)
                except SyntaxError as exc:
                    record.syntax_error = "line {}: {}".format(
                        exc.lineno or 0, exc.msg
                    )
                else:
                    visitor = _SymbolVisitor(relative_name)
                    visitor.visit(tree)
                    record.symbols = visitor.symbols
                    record.import_names = _collect_import_names(tree, relative)

                self.files[relative_name] = record
                modules[_module_name(relative)] = relative_name

        _resolve_imports(self.files, modules)

    def search_symbols(self, query: str, limit: int = 20) -> List[dict]:
        query = query.strip().casefold()
        if not query:
            raise ValueError("query must not be empty")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")

        matches = [
            symbol
            for record in self.files.values()
            for symbol in record.symbols
            if query in symbol.qualified_name.casefold()
        ]
        matches.sort(
            key=lambda symbol: (
                symbol.qualified_name.casefold() != query,
                symbol.qualified_name.casefold().find(query),
                symbol.path,
                symbol.line,
            )
        )
        return [
            {
                "name": item.name,
                "qualified_name": item.qualified_name,
                "kind": item.kind,
                "path": item.path,
                "line": item.line,
                "end_line": item.end_line,
            }
            for item in matches[:limit]
        ]

    def file_outline(self, path: str) -> dict:
        record = self._get_file(path)
        return {
            "path": record.path,
            "lines": record.line_count,
            "syntax_error": record.syntax_error,
            "symbols": [
                {
                    "name": item.name,
                    "qualified_name": item.qualified_name,
                    "kind": item.kind,
                    "line": item.line,
                    "end_line": item.end_line,
                }
                for item in record.symbols
            ],
            "imports": sorted(record.imports),
        }

    def read_source(
        self, path: str, start_line: int = 1, end_line: Optional[int] = None
    ) -> dict:
        record = self._get_file(path)
        if isinstance(start_line, bool) or not isinstance(start_line, int):
            raise ValueError("start_line must be an integer")
        if isinstance(end_line, bool) or (
            end_line is not None and not isinstance(end_line, int)
        ):
            raise ValueError("end_line must be an integer")
        if start_line < 1:
            raise ValueError("start_line must be at least 1")
        last_line = (
            max(record.line_count, start_line) if end_line is None else end_line
        )
        if last_line < start_line:
            raise ValueError("end_line must not be before start_line")
        if last_line - start_line + 1 > MAX_SOURCE_LINES:
            raise ValueError(
                "source range must not exceed {} lines".format(MAX_SOURCE_LINES)
            )

        source = self._read_source(record)
        lines = source.splitlines()
        selected = lines[start_line - 1 : last_line]
        return {
            "path": record.path,
            "start_line": start_line,
            "end_line": start_line + len(selected) - 1 if selected else start_line - 1,
            "content": "\n".join(selected),
            "total_lines": record.line_count,
        }

    def search_text(self, query: str, limit: int = 50) -> dict:
        query = query.strip().casefold()
        if not query:
            raise ValueError("query must not be empty")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise ValueError("limit must be an integer between 1 and 100")

        matches = []
        truncated = False
        for path in sorted(self.files):
            for line_number, line in enumerate(
                self._read_source(self.files[path]).splitlines(), start=1
            ):
                if query not in line.casefold():
                    continue
                if len(matches) == limit:
                    truncated = True
                    break
                matches.append(
                    {"path": path, "line": line_number, "text": line.strip()}
                )
            if truncated:
                break
        return {"matches": matches, "truncated": truncated}

    def dependency_impact(self, path: str) -> dict:
        record = self._get_file(path)
        reverse = self._reverse_dependencies()
        impacted = self._transitive_dependents([record.path], reverse)
        return {
            "path": record.path,
            "direct_dependents": sorted(reverse.get(record.path, set())),
            "transitive_dependents": sorted(impacted),
            "count": len(impacted),
        }

    def architecture_map(self, limit: int = 100) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer between 1 and 200")

        graph = {
            path: sorted(record.imports) for path, record in self.files.items()
        }
        reverse = self._reverse_dependencies()
        selected_paths = sorted(graph)[:limit]
        selected = set(selected_paths)
        edges = [
            {"from": path, "to": target}
            for path in selected_paths
            for target in graph[path]
            if target in selected
        ]
        cycles = self._dependency_cycles(graph)
        return {
            "modules": [
                {
                    "path": path,
                    "fan_in": len(reverse.get(path, set())),
                    "fan_out": len(graph[path]),
                }
                for path in selected_paths
            ],
            "edges": edges,
            "total_modules": len(graph),
            "total_edges": sum(len(targets) for targets in graph.values()),
            "truncated": len(graph) > limit,
            "cycles": cycles[:50],
            "cycles_truncated": len(cycles) > 50,
        }

    def repository_health(self) -> dict:
        records = list(self.files.values())
        line_count = sum(item.line_count for item in records)
        large_files = [
            {"path": item.path, "lines": item.line_count}
            for item in records
            if item.line_count > LARGE_FILE_LINES
        ]
        syntax_errors = [
            {"path": item.path, "error": item.syntax_error}
            for item in records
            if item.syntax_error
        ]
        large_files.sort(key=lambda item: (-item["lines"], item["path"]))
        syntax_errors.sort(key=lambda item: item["path"])
        score = max(
            0,
            100
            - len(syntax_errors) * 20
            - len(large_files) * 5
            - len(self.warnings) * 2,
        )
        return {
            "repository": self.root.name,
            "python_files": len(records),
            "lines": line_count,
            "symbols": sum(len(item.symbols) for item in records),
            "health_score": score,
            "large_files": large_files,
            "syntax_errors": syntax_errors,
            "warnings": sorted(self.warnings),
        }

    def change_risk(self, paths: List[str]) -> dict:
        if not paths:
            raise ValueError("paths must contain at least one indexed Python file")
        if len(paths) > 100:
            raise ValueError("paths must contain at most 100 files")

        changed = sorted({self._get_file(path).path for path in paths})
        reverse = self._reverse_dependencies()
        impacted = self._transitive_dependents(changed, reverse)
        impacted_tests = sorted(
            path
            for path in impacted
            if Path(path).name.startswith("test_")
            or Path(path).name.endswith("_test.py")
            or "tests" in Path(path).parts
        )
        changed_tests = [
            path
            for path in changed
            if Path(path).name.startswith("test_")
            or Path(path).name.endswith("_test.py")
            or "tests" in Path(path).parts
        ]
        large_changed = [
            path
            for path in changed
            if self.files[path].line_count > LARGE_FILE_LINES
        ]

        score = min(
            100,
            15
            + len(impacted) * 8
            + len(large_changed) * 10
            + (20 if not changed_tests and not impacted_tests else 0),
        )
        return {
            "risk_score": score,
            "risk_level": (
                "high" if score >= 70 else "medium" if score >= 40 else "low"
            ),
            "changed_files": changed,
            "impacted_files": sorted(impacted),
            "impacted_tests": impacted_tests,
            "rationale": [
                "{} dependent Python file(s) may need review".format(len(impacted)),
                "{} changed file(s) exceed {} lines".format(
                    len(large_changed), LARGE_FILE_LINES
                ),
                (
                    "No related test file was found in the indexed dependency graph"
                    if not changed_tests and not impacted_tests
                    else "Related test files are present in the changed or impacted set"
                ),
            ],
            "scoring_note": (
                "Heuristic based on local imports, file size, and test proximity; "
                "not a substitute for running tests."
            ),
        }

    def _get_file(self, path: str) -> FileRecord:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path must be a non-empty repository-relative path")
        candidate = (self.root / path).resolve()
        if not _inside_root(candidate, self.root):
            raise ValueError("path must stay inside the repository root")
        relative = candidate.relative_to(self.root).as_posix()
        record = self.files.get(relative)
        if record is None:
            raise ValueError("Python file is not in the index: {}".format(path))
        return record

    def _read_source(self, record: FileRecord) -> str:
        candidate = self.root / record.path
        try:
            if candidate.is_symlink():
                raise ValueError("refusing to read a symlink: {}".format(record.path))
            resolved = candidate.resolve()
            if not _inside_root(resolved, self.root):
                raise ValueError(
                    "path must stay inside the repository root: {}".format(record.path)
                )
            with resolved.open("rb") as source_file:
                source_bytes = source_file.read(MAX_SOURCE_BYTES + 1)
            if len(source_bytes) > MAX_SOURCE_BYTES:
                raise ValueError(
                    "file exceeds the {} byte limit: {}".format(
                        MAX_SOURCE_BYTES, record.path
                    )
                )
            return source_bytes.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(
                "could not read indexed file {}: {}".format(record.path, exc)
            ) from exc

    def _reverse_dependencies(self) -> Dict[str, Set[str]]:
        reverse = defaultdict(set)
        for path, record in self.files.items():
            for dependency in record.imports:
                reverse[dependency].add(path)
        return reverse

    @staticmethod
    def _dependency_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
        reverse = {node: [] for node in graph}
        for node, targets in graph.items():
            for target in targets:
                reverse[target].append(node)

        visited = set()
        finish_order = []
        for root in sorted(graph):
            if root in visited:
                continue
            visited.add(root)
            stack = [(root, iter(graph[root]))]
            while stack:
                node, neighbors = stack[-1]
                try:
                    neighbor = next(neighbors)
                except StopIteration:
                    finish_order.append(node)
                    stack.pop()
                else:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append((neighbor, iter(graph[neighbor])))

        visited.clear()
        cycles = []
        for root in reversed(finish_order):
            if root in visited:
                continue
            component = []
            pending = [root]
            visited.add(root)
            while pending:
                node = pending.pop()
                component.append(node)
                for neighbor in reverse[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        pending.append(neighbor)
            if len(component) > 1:
                cycles.append(sorted(component))
        cycles.sort()
        return cycles

    @staticmethod
    def _transitive_dependents(
        paths: List[str], reverse: Dict[str, Set[str]]
    ) -> Set[str]:
        visited = set()
        pending = deque(paths)
        while pending:
            current = pending.popleft()
            for dependent in reverse.get(current, set()):
                if dependent not in paths and dependent not in visited:
                    visited.add(dependent)
                    pending.append(dependent)
        return visited

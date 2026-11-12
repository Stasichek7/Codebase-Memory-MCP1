# Python migration

This fork targets a full Python implementation of the C server and CBM Lens
features. The full port remains to be implemented. The working native core and
frontend remain the behavioral reference while Python replacements are developed.
Retain each original component until equivalent behavior has passed acceptance
tests through its supported entry points.

## Current implementation

The experimental backend in `pkg/pypi/src/codebase_memory_mcp/python_backend`
uses the Python standard library to index Python AST definitions and local
imports. It serves newline-delimited MCP JSON-RPC over standard input and output,
holds a single repository snapshot in memory, and refreshes it on request.

Its nine tools are `index_repository`, `search_symbols`, `file_outline`,
`read_source`, `search_text`, `dependency_impact`, `architecture_map`,
`repository_health`, and `change_risk`. Source reads are capped at 200 lines,
files above 2,000,000 bytes are skipped, and health and risk scores use heuristics.
The standalone `health_analyzer` adds source-size reports across its supported
extensions. Python packaging currently also includes a native runtime downloader.

The following tables describe the required migration scope. A related Python
capability identifies reusable work. Full compatibility remains to be verified
for every row, including rows with an existing Python capability.

## MCP tools

| Native tool | Required behavior | Existing Python capability |
|---|---|---|
| `index_repository` | Multi-language project indexes, refresh, async jobs, cancellation, status, publication, watch registration | Same tool name indexes a configured Python root in memory |
| `list_projects` | Project registry, paging and statistics | Pending |
| `delete_project` | Consistent removal of project indexes and ADR sidecars | Pending |
| `index_status` | Published index state and freshness | Pending |
| `check_index_coverage` | Path and scope coverage, exclusions, parse gaps and freshness | Pending |
| `search_graph` | Structural, BM25 and semantic search with independent pagination | `search_symbols` searches Python definitions |
| `trace_path` | Calls, data flow, cross-service, topology, deployment and execution paths | `dependency_impact` follows local Python imports |
| `detect_changes` | Git diff to affected symbols, blast radius and risk | `change_risk` accepts explicit Python file paths |
| `query_graph` | Read-only Cypher-like queries | Pending |
| `get_graph_schema` | Labels, properties, counts and relationship patterns | Pending |
| `compare_graphs` | Additions and removals between indexed snapshots | Pending |
| `get_code_snippet` | Symbol lookup and source retrieval | `read_source` reads a Python file range |
| `get_file_outline` | Source-ordered declarations, filters and paging | `file_outline` provides Python definitions and imports |
| `get_architecture` | Languages, packages, routes, hotspots, clusters and ADR | `architecture_map` provides a Python import graph and cycles |
| `search_code` | Text search across indexed project files | `search_text` searches indexed Python files |
| `manage_adr` | Reads, updates and section operations preserving unrelated document bytes | Pending |
| `ingest_traces` | Labeled observed call paths with symbol resolution and unresolved-name reporting | Pending |

## Server and Lens scope

| Area | Required acceptance scope | Current Python status |
|---|---|---|
| Native entry points | MCP stdio, one-shot CLI, daemon start/status/stop, config, install/update/uninstall, supported client integrations and hooks | Experimental stdio server and health-report CLI |
| Coordination | Session ownership, admission barriers, project locks, concurrent readers/writers, worker supervision, cancellation and recovery | Pending |
| Persistence | SQLite graph/schema compatibility, transactions, published generations, restart recovery, snapshots and artifacts | In-memory Python snapshot |
| Discovery and sync | Ignore layers, custom extensions, path containment, symlinks, worktrees, freshness and watchers | Fixed exclusions and root containment for Python files |
| Language intelligence | Supported grammar registry and extraction, cross-file relationships, Hybrid LSP and type/call resolution | Python definitions and local imports |
| System relationships | Documentation and PDF text, infrastructure/deployment links, ADRs, observed traces, Smart CI and test impact | Pending |
| Local HTTP service | Loopback serving, RPC and Lens API contracts, project browsing/indexing and configuration | Pending |
| Explore | File tree, highlighted source, selection, file impact, symbol details and related tests | Existing browser implementation requires a compatible Python service |
| Galaxy | Graph search, hierarchy, expansion, paths, navigation and coverage evidence | Existing browser implementation requires a compatible Python service |
| Architecture | Overview, entry points, routes, hotspots, system structure and behavior paths | Existing browser implementation requires a compatible Python service |
| ADR and Coverage | Explicit document saves, conflict handling, indexing gaps and freshness | Existing browser implementation requires a compatible Python service |
| System | Daemon activity, indexes, logs and filters | Existing browser implementation requires a compatible Python service |
| Local model and chat | Opt-in model downloads, browser WebGPU inference, cached loading, selected-code context, graph answers, labels and limits | Existing browser implementation and assets remain to integrate and verify |

Required browser JavaScript may remain in the final implementation. Server logic,
analysis, storage, jobs and API handlers are migration targets for Python.

## Language measurement

The target is at least 90% Python by bytes of maintained first-party executable
source. Count runtime code, headers, CLI code, browser source, tests and executable
tooling. Report the tracked revision, included paths, exclusions, bytes per
language, and `Python source bytes / all included source bytes` reproducibly.

Exclude vendored dependencies, generated parsers and bundles, documentation,
media, lockfiles and build outputs. Existing first-party C and browser source
remain in the denominator while maintained. Classify source by its actual
language. Language overrides, renaming unrelated code as Python and padding do
not satisfy the target. The remaining languages, including necessary browser
JavaScript or TypeScript, together must fit within 10%.

## Delivery order and acceptance

1. Capture the native baseline. Inventory tool schemas, CLI behavior, persisted
   data, HTTP routes and Lens workflows at a recorded revision. Build contract
   fixtures with successful responses, failures, limits and cancellation cases.
2. Establish Python packaging and entry points. Route Python commands directly
   to Python implementations. Verify clean installation, stdio framing, errors,
   supported platforms and startup without a native downloader.
3. Implement persistence and coordination. Verify existing data migration,
   transactional publication, concurrent requests, daemon lifecycle, worker
   failure, interruption, retry and restart recovery.
4. Port discovery and analysis. Run shared language fixtures through both
   implementations. Verify extraction and resolution, ignore behavior, coverage,
   incremental refresh, watchers and configured resource limits.
5. Complete all 17 MCP tool contracts and system relationships. Compare schemas,
   pagination, errors and results using the same fixtures. Cover documentation,
   infrastructure, ADR preservation, traces, snapshots and test-impact behavior.
6. Integrate Lens with the Python HTTP service. Run browser acceptance tests for
   every workspace, configuration, source selection, graph navigation, ADR saves,
   indexing progress and local-model/chat behavior.
7. Validate release and retire replaced components. Verify installation, upgrades,
   client integrations, hooks, cross-platform operation and measured performance.
   Retire original components only after their replacement acceptance passes,
   then publish the measured source-language share.

Completion requires all of the following evidence.

- [ ] Equivalent behavior for all 17 native MCP tools through MCP and CLI.
- [ ] Persistent data, daemon, concurrency, watchers and failure recovery pass.
- [ ] Supported languages, Hybrid LSP and system relationships pass shared fixtures.
- [ ] Every Lens workspace and local-model workflow passes browser acceptance.
- [ ] Packaging, upgrades and supported client integrations pass on each platform.
- [ ] Resource use and latency are measured against the recorded native baseline.
- [ ] First-party executable source measures at least 90% Python by the rule above.
- [ ] README claims and installation instructions match the verified implementation.

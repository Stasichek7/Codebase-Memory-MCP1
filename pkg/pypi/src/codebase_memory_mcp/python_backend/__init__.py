"""Pure-Python MCP backend for Python repository analysis."""


def main(argv=None):
    from .server import main as run

    return run(argv)

__all__ = ["main"]

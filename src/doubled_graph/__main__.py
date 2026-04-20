"""`python -m doubled_graph` → start MCP server on stdio."""

from doubled_graph.cli import main

if __name__ == "__main__":
    main(argv_default=["serve"])

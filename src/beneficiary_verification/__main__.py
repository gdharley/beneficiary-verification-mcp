"""CLI entrypoint for running the MCP server over HTTP."""

import os

from .server import mcp


def main() -> None:
    port = int(os.environ.get("PORT", 9000))
    host = os.environ.get("HOST", "127.0.0.1")
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()

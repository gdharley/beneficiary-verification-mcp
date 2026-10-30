"""CLI entrypoint for running the MCP server over HTTP."""

from .server import mcp


def main() -> None:
    mcp.run(transport="http", host="127.0.0.1", port=9000)


if __name__ == "__main__":
    main()

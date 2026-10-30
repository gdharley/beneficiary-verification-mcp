# simple-mcp-server

A minimal Python starter project for building an MCP server with FastMCP.

It currently exposes one tool:

- `add(a, b)`: returns the sum of two numbers

## Requirements

- Python 3.12+

## Install

If you want the project installed into the current virtual environment:

```bash
./.venv/bin/pip install -e .
```

## Run the server

Run over HTTP on port `9000`.

Without installing the package, point Python at the `src/` tree:

```bash
PYTHONPATH=src ./.venv/bin/python -m simple_mcp_server
```

Or, after installing the package:

```bash
./.venv/bin/simple-mcp-server
```

The MCP HTTP endpoint will be available at:

```text
http://127.0.0.1:9000/mcp
```

## Try the tool from a client

This opens an in-process MCP client and calls the `add` tool:

```bash
./.venv/bin/python - <<'PY'
import asyncio
from fastmcp import Client

from simple_mcp_server.server import mcp

async def main():
    async with Client(mcp) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        print(result.content[0].text)

asyncio.run(main())
PY
```

Expected output:

```text
5.0
```

## Run tests

```bash
PYTHONPATH=src ./.venv/bin/python -m unittest discover -s tests -v
```

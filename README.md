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

## Deploy to Render

The repo includes a `render.yaml` blueprint. In Render, choose **New > Blueprint**
and point it at this repository; it provisions a single web service.

Two environment variables drive the bind address:

- `HOST`: set to `0.0.0.0` by the blueprint so Render can route to the container.
  Defaults to `127.0.0.1` locally.
- `PORT`: injected by Render. Defaults to `9000` locally.

Once deployed, the MCP endpoint is:

```text
https://<service-name>.onrender.com/mcp
```

Note: the blueprint sets no `healthCheckPath`. A plain `GET /mcp` returns `406`
because the transport requires an SSE-capable `Accept` header, so a health check
against it would fail the deploy. Render falls back to port detection instead.

On the free plan the service sleeps after ~15 minutes idle, and the next request
pays a cold start of roughly 30 seconds.

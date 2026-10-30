"""FastMCP server definition for the starter project."""

import logging

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Simple MCP Server")


@mcp.tool
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    logger.info("add called with a=%s b=%s", a, b)
    return a + b

import unittest

from fastmcp import Client

from simple_mcp_server.server import mcp


class AddToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_add_returns_sum(self) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool("add", {"a": 2, "b": 3})

        self.assertEqual(result.content[0].text, "5.0")

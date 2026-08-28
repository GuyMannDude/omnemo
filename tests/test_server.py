"""MCP server surface: exactly four tools, wired to the store."""

import asyncio
import json

from omnemo.server import build_server
from omnemo.store import Store


def test_exposes_exactly_four_tools(store: Store) -> None:
    server = build_server(store)
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == ["forget", "recall", "save", "search"]


def test_tools_round_trip(store: Store) -> None:
    server = build_server(store)

    def call(name: str, arguments: dict):
        result = asyncio.run(server.call_tool(name, arguments))
        assert not result.is_error
        # List-returning tools arrive as {"result": [...]} in structured
        # content; dict-returning tools as plain JSON text.
        if result.structured_content is not None:
            return result.structured_content.get("result", result.structured_content)
        return json.loads(result.content[0].text)

    saved = call("save", {"text": "The router password is taped under the desk"})
    assert saved["category"] == "fact"

    recalled = call("recall", {"query": "where is the router password"})
    assert recalled[0]["id"] == saved["id"]

    found = call("search", {"query": "router"})
    assert [m["id"] for m in found] == [saved["id"]]

    assert call("forget", {"id": saved["id"]}) == {"forgotten": True}
    assert call("recall", {"query": "where is the router password"}) == []

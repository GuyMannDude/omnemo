"""MCP server over stdio exposing exactly four tools:
save, recall, search, forget.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import __version__
from .config import load_config, store_path
from .embedder import make_embedder
from .store import Store


def build_server(store: Store) -> MCPServer:
    server = MCPServer(
        name="omnemo",
        version=__version__,
        instructions=(
            "Personal long-term memory. Save durable facts, decisions, "
            "preferences, and incidents; recall by meaning before answering "
            "questions the user may have covered before; forget on request."
        ),
    )

    categories = ", ".join(sorted(store.config.categories))

    @server.tool(
        name="save",
        description=(
            "Save one memory. Use for durable facts, decisions, preferences, "
            f"and incidents — not transient state. Categories: {categories}."
        ),
    )
    def save(text: str, category: str | None = None) -> dict:
        memory = store.save(text, category)
        return {"id": memory.id, "category": memory.category}

    @server.tool(
        name="recall",
        description=(
            "Recall memories by meaning (semantic similarity, ranked by "
            "relevance, recency, and importance). Query in natural language."
        ),
    )
    def recall(query: str, limit: int | None = None) -> list[dict]:
        return [
            {
                "id": r.memory.id,
                "text": r.memory.text,
                "category": r.memory.category,
                "similarity": round(r.similarity, 4),
                "score": round(r.score, 4),
            }
            for r in store.recall(query, limit)
        ]

    @server.tool(
        name="search",
        description="Search memories by literal substring (case-insensitive).",
    )
    def search(query: str, limit: int = 20) -> list[dict]:
        return [
            {"id": m.id, "text": m.text, "category": m.category}
            for m in store.search(query, limit)
        ]

    @server.tool(
        name="forget",
        description=(
            "Permanently delete a memory by id (from save/recall/search). "
            "It is removed from the store, not just hidden."
        ),
    )
    def forget(id: int) -> dict:
        return {"forgotten": store.forget(id)}

    return server


def serve() -> None:
    """Run the MCP server on stdio with the configured store and embedder,
    warming the embedder first so the first recall is fast."""
    config = load_config()
    embedder = make_embedder(config.embedder)
    embedder.warm_up()
    store = Store(store_path(), embedder, config)
    build_server(store).run("stdio")

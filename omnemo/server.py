"""MCP server over stdio exposing exactly four tools:
save, recall, search, forget.
"""

from __future__ import annotations

import sys

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
            f"and incidents — not transient state. Categories: {categories}. "
            "Returns near_duplicates (older memories saying nearly the same "
            "thing); pass their ids as supersedes when this text replaces them."
        ),
    )
    def save(
        text: str,
        category: str | None = None,
        supersedes: list[int] | None = None,
    ) -> dict:
        """`supersedes`: ids this memory replaces — they stop being recalled.
        The reply names near-duplicates already stored, so a caller can
        save again with `supersedes` when the new text is the current truth."""
        result = store.save(text, category, supersedes)
        return {
            "id": result.id,
            "category": result.category,
            "near_duplicates": [
                {"id": n.memory.id, "text": n.memory.text, "similarity": round(n.similarity, 4)}
                for n in result.near_duplicates
            ],
        }

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
    def search(query: str, limit: int | None = None) -> list[dict]:
        return [
            {"id": m.id, "text": m.text, "category": m.category,
             "superseded_by": m.superseded_by}
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
    try:
        embedder.warm_up()
    except Exception as exc:
        print(
            f"error: embedder {config.embedder!r} failed to load: {exc} "
            "(first run downloads the model, which needs network access once)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    store = Store(store_path(), embedder, config)
    build_server(store).run("stdio")

"""CLI: `omnemo serve` runs the MCP server; save/recall/search/forget are
direct verbs for testing; `omnemo stats` is the stats-only digest source.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from . import __version__
from .config import load_config, store_path
from .embedder import make_embedder
from .store import EmbedderMismatchError, Store


def _open_store() -> Store:
    config = load_config()
    embedder = make_embedder(config.embedder)
    return Store(store_path(), embedder, config)


def _fmt_time(ts: float | None) -> str:
    if ts is None:
        return "never"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omnemo", description="Memory-only MCP server."
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="run the MCP server on stdio")

    p_save = sub.add_parser("save", help="save one memory")
    p_save.add_argument("text")
    p_save.add_argument("--category", "-c", default=None)

    p_recall = sub.add_parser("recall", help="recall memories by meaning")
    p_recall.add_argument("query")
    p_recall.add_argument("--limit", "-n", type=int, default=None)

    p_search = sub.add_parser("search", help="search memories by substring")
    p_search.add_argument("query")
    p_search.add_argument("--limit", "-n", type=int, default=20)

    p_forget = sub.add_parser("forget", help="permanently delete a memory by id")
    p_forget.add_argument("id", type=int)

    sub.add_parser("stats", help="memory count, learned today, last recall")

    args = parser.parse_args(argv)

    if args.command == "serve":
        from .server import serve

        serve()
        return 0

    try:
        store = _open_store()
    except EmbedderMismatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        if args.command == "save":
            try:
                memory = store.save(args.text, args.category)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            print(f"saved #{memory.id} [{memory.category}]")

        elif args.command == "recall":
            results = store.recall(args.query, args.limit)
            if not results:
                print("no memories recalled")
            for r in results:
                print(
                    f"#{r.memory.id} [{r.memory.category}] "
                    f"score={r.score:.3f} sim={r.similarity:.3f}  {r.memory.text}"
                )

        elif args.command == "search":
            memories = store.search(args.query, args.limit)
            if not memories:
                print("no matches")
            for m in memories:
                print(f"#{m.id} [{m.category}]  {m.text}")

        elif args.command == "forget":
            if store.forget(args.id):
                print(f"forgot #{args.id}")
            else:
                print(f"error: no memory #{args.id}", file=sys.stderr)
                return 1

        elif args.command == "stats":
            s = store.stats()
            print(f"memories:      {s['memory_count']}")
            print(f"learned today: {s['learned_today']}")
            print(f"last recall:   {_fmt_time(s['last_recall_at'])}")
    finally:
        store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

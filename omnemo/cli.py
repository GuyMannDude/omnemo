"""CLI: `omnemo serve` runs the MCP server; save/recall/search/forget are
direct verbs for testing; `omnemo stats` is the stats-only digest source.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from . import __version__
from .config import ConfigError, load_config, store_path
from .embedder import make_embedder
from .store import CorruptStoreError, EmbedderMismatchError, Store

# Anything the store/config layer reports as a clean, named error.
_KNOWN_ERRORS = (ConfigError, CorruptStoreError, EmbedderMismatchError)


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
    p_search.add_argument("--limit", "-n", type=int, default=None)

    p_forget = sub.add_parser("forget", help="permanently delete a memory by id")
    p_forget.add_argument("id", type=int)

    p_stats = sub.add_parser(
        "stats", help="memory count, learned today, last recall"
    )
    p_stats.add_argument("--json", action="store_true", dest="as_json")

    sub.add_parser("warm", help="pre-load the embedder (boot warm-up)")

    sub.add_parser(
        "setup",
        help="install the Omarchy glove: skill, bar plugin, warm-up, connect",
    )
    sub.add_parser("connect", help="register the MCP server with every harness")
    p_disc = sub.add_parser("disconnect", help="unregister from every harness")
    p_disc.add_argument(
        "--all-pieces", action="store_true",
        help="also remove skill links, bar plugin, and warm-up unit",
    )

    args = parser.parse_args(argv)

    if args.command in ("setup", "connect", "disconnect"):
        from .omarchy import glove
        from .omarchy.harnesses import connect_all, disconnect_all

        if args.command == "setup":
            lines, results = glove.setup()
        elif args.command == "connect":
            lines, results = [], connect_all()
        elif getattr(args, "all_pieces", False):
            lines, results = glove.teardown()
        else:
            lines, results = [], disconnect_all()
        for line in lines:
            print(line)
        failed = False
        for r in results:
            mark = "ok " if r.ok else "FAIL"
            detail = f" — {r.detail}" if r.detail else ""
            print(f"[{mark}] {r.harness}: {r.action}{detail}")
            failed = failed or not r.ok
        return 1 if failed else 0

    if args.command == "warm":
        try:
            config = load_config()
            embedder = make_embedder(config.embedder)
            embedder.embed(["omnemo warm-up"])
        except _KNOWN_ERRORS as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print("embedder warm")
        return 0

    if args.command == "serve":
        from .server import serve

        try:
            serve()
        except _KNOWN_ERRORS as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0

    try:
        store = _open_store()
    except _KNOWN_ERRORS as e:
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
            if args.as_json:
                import json

                print(json.dumps(s))
            else:
                print(f"memories:      {s['memory_count']}")
                print(f"learned today: {s['learned_today']}")
                print(f"last recall:   {_fmt_time(s['last_recall_at'])}")
    finally:
        store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

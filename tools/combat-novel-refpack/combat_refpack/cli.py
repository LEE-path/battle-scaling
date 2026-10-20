"""JSON CLI with explicit local paths. No model backend is called implicitly."""
import argparse
import json
import sys

from . import core


def parser():
    ap = argparse.ArgumentParser(description="Offline combat novel evidence reference packets")
    sub = ap.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Create a new immutable source bundle")
    for argument in ("source", "output", "work", "edition"):
        prepare.add_argument("--" + argument, required=True)
    prepare.add_argument("--encoding")
    search = sub.add_parser("search", help="Literal navigation only; does not mark text read")
    search.add_argument("--bundle", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=20)
    tasks = sub.add_parser("tasks", help="Emit ending-backwards current-Agent reading tasks")
    tasks.add_argument("--bundle", required=True)
    tasks.add_argument("--max-chars", type=int, default=12000)
    accept = sub.add_parser("accept", help="Validate and preserve an Agent/human JSON receipt")
    accept.add_argument("--bundle", required=True)
    accept.add_argument("--input", required=True)
    for name in ("build", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--bundle", required=True)
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        args = parser().parse_args(argv)
        if args.command == "prepare":
            result = core.prepare(args.source, args.output, args.work, args.edition, args.encoding)
        elif args.command == "search":
            result = core.search(args.bundle, args.query, args.limit)
        elif args.command == "tasks":
            result = core.tasks(args.bundle, args.max_chars)
        elif args.command == "accept":
            result = core.accept(args.bundle, args.input)
        elif args.command == "build":
            result = core.build(args.bundle)
        else:
            result = core.verify(args.bundle)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

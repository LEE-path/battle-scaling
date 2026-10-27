"""JSON CLI with explicit local paths. No model backend is called implicitly."""
import argparse
import json
import sys
from pathlib import Path

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
    tasks.add_argument('--summary', action='store_true', help='Print task counts and paths without the full book text')
    next_task = sub.add_parser('next', help='Bounded ending-backwards batch; never marks reading complete')
    next_task.add_argument('--bundle', required=True)
    next_task.add_argument('--limit', type=int, default=3)
    next_task.add_argument('--max-chars', type=int, default=24000)
    accept = sub.add_parser("accept", help="Validate and preserve an Agent/human JSON receipt")
    accept.add_argument("--bundle", required=True)
    accept.add_argument("--input", required=True)
    batch = sub.add_parser('accept-batch', help='Accept actual read reviews together and retain partial progress')
    batch.add_argument('--bundle', required=True)
    batch.add_argument('--input', required=True)
    synthesis = sub.add_parser('synthesize', help='Evidence-led cross-chapter work for explicitly confirmed aliases')
    synthesis.add_argument('--bundle', required=True)
    synthesis.add_argument('--subject', required=True)
    synthesis.add_argument('--alias', action='append', default=[])
    synthesis.add_argument('--target-state')
    for name in ("build", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--bundle", required=True)
    for name, command in sub.choices.items():
        command.add_argument('--result-output' if name == 'prepare' else '--output', dest='json_output',
                            help='Save the complete result outside the bundle; stdout becomes a short summary')
        command.add_argument('--full-output', action='store_true')
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        args = parser().parse_args(argv)
        if args.json_output:
            destination = Path(args.json_output).expanduser().resolve()
            bundle = Path(args.output if args.command == 'prepare' else args.bundle).expanduser().resolve()
            if destination.is_relative_to(bundle):
                raise ValueError('Result JSON must be outside the immutable book bundle')
            manifest = bundle/'manifest.json'
            original = args.source if args.command == 'prepare' else (
                core.read_json(manifest).get('source_original_path') if manifest.exists() else None)
            if original and destination == Path(original).expanduser().resolve():
                raise ValueError('Result JSON cannot overwrite the original book')
        if args.command == "prepare":
            result = core.prepare(args.source, args.output, args.work, args.edition, args.encoding)
        elif args.command == "search":
            result = core.search(args.bundle, args.query, args.limit)
        elif args.command == "tasks":
            result = core.tasks(args.bundle, args.max_chars)
            if args.summary:
                result = {key:value for key,value in result.items() if key!='tasks'}
        elif args.command == 'next':
            result = core.next_batch(args.bundle, args.limit, args.max_chars)
        elif args.command == "accept":
            result = core.accept(args.bundle, args.input)
        elif args.command == 'accept-batch':
            result = core.accept_batch(args.bundle, args.input)
        elif args.command == 'synthesize':
            result = core.synthesize(args.bundle, args.subject, args.alias, args.target_state)
        elif args.command == "build":
            result = core.build(args.bundle)
        else:
            result = core.verify(args.bundle)
        if args.json_output:
            core.write_json(args.json_output, result)
        shown = ({'status':result['status'],'output':str(args.json_output),
                  **{k:result[k] for k in ('task_count','pending_task_count','source_characters','semantic_complete') if k in result}}
                 if args.json_output and not args.full_output else result)
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

"""Inspection commands; no network or model download unless explicitly configured."""
import argparse
import json
from .api import Knowledge
from .demo import demonstrate
from .embeddings import NomicHTTPEmbedding, TestEmbedding
from .live import LiveStore
from . import research_cli


def main():
    parser = argparse.ArgumentParser(prog="mira")
    parser.add_argument("--root", default="knowledge")
    parser.add_argument("--live", action="store_true", help="explicitly use live canonical storage")
    parser.add_argument("--test-embedding", action="store_true", help="token-hash test double, not semantic retrieval")
    parser.add_argument("--embedding-url")
    parser.add_argument("--model-identity")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "rebuild", "integrity", "summaries", "demo"):
        sub.add_parser(command)
    research_cli.register(sub)
    recovery = sub.add_parser("recovery")
    recovery.add_argument("recovery_action", nargs="?", choices=["inspect", "validate", "repair"], default="inspect")
    recovery.add_argument("operation_id", nargs="?")
    recovery.add_argument("--apply", action="store_true", help="explicitly finish the named operation")
    create = sub.add_parser("create")
    create.add_argument("title")
    create.add_argument("summary")
    create.add_argument("--kind", choices=["research", "synthesis"], default="research")
    get = sub.add_parser("get")
    get.add_argument("reference")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--mode", choices=["fulltext", "vector"], default="fulltext")
    edges = sub.add_parser("relationships")
    edges.add_argument("reference")
    edges.add_argument("--direction", choices=["incoming", "outgoing"], default="outgoing")
    edges.add_argument("--status", action="append")
    args = parser.parse_args()
    if args.command in {"research-init", "research-run", "research-state", "transcript"}:
        result = research_cli.execute(args)
        print(result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.test_embedding and args.embedding_url:
        parser.error("choose one embedding backend")
    if args.embedding_url and not args.model_identity:
        parser.error("--model-identity required with --embedding-url")
    backend = NomicHTTPEmbedding(args.embedding_url, args.model_identity) if args.embedding_url else TestEmbedding() if args.test_embedding else None
    if args.command == "demo" and args.live:
        parser.error("demo uses Phase 1 storage; omit --live")
    if args.command == "recovery":
        if args.recovery_action == "repair" and (not args.live or not args.operation_id):
            parser.error("repair requires --live and an operation ID")
        if args.apply and args.recovery_action != "repair":
            parser.error("--apply is only valid for repair")
        if args.operation_id and args.recovery_action != "repair":
            parser.error("operation ID is only valid for repair")
    k = Knowledge(args.root, backend, store=LiveStore(args.root) if args.live else None)
    if args.command == "demo":
        result = demonstrate(args.root, backend)
    elif args.command == "create":
        result = k.create_memory(args.title, args.summary, kind=args.kind).__dict__
    elif args.command == "get":
        result = k.retrieve(args.reference)
    elif args.command == "search":
        result = k.search(args.query, mode=args.mode)
    elif args.command == "relationships":
        options = {"statuses": args.status} if args.status else {}
        result = k.relationships(args.reference, direction=args.direction, **options)
    elif args.command == "recovery":
        result = (k.store.repair(args.operation_id, apply=args.apply)
                  if args.recovery_action == "repair" else k.store.recovery_status())
    elif args.command == "integrity":
        result = k.directory.integrity()
    else:
        result = getattr(k, args.command)()
    print(result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

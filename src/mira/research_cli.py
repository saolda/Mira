"""Research CLI. Transcript reads independent records without opening a corpus."""
from pathlib import Path

from .format import dumps, loads
from .interactions import transcript
from .research import Research
from .decisions import ScriptedLLM
from .search import FixtureSearch
from .experiments import Experiments
from .format import require


def register(sub):
    init = sub.add_parser("research-init")
    init.add_argument("question", nargs="?", help="research question (alternative to --question-file)")
    init.add_argument("--question-file", metavar="PATH", help="Markdown question, optional context and research objectives")
    init.add_argument("--disposable", action="store_true", help="designate this development experiment for explicit cleanup after completion")
    selection = init.add_mutually_exclusive_group()
    selection.add_argument("--database", action="append", help="explicit database sequence (compatibility)")
    selection.add_argument("--strategy", help="named strategy; omit for mandatory R0 selection")
    init.add_argument("--strategies", help="JSON strategy registry (or MIRA_RESEARCH_STRATEGIES)")
    init.add_argument("--query-profiles", help="JSON query-profile registry (or MIRA_QUERY_PROFILES); snapshotted at initialization")
    init.add_argument("--synthesis-interval", type=int, default=5)
    init.add_argument("--context-budget", type=int, help="model token budget; default to the active server context window")
    init.add_argument("--output-reserve", type=int, default=2048)
    init.add_argument("--synthesis-output-reserve", type=int, help="optional separate reserve for synthesis output")
    init.add_argument("--research-capacity-tokens", type=int, help="R5 estimated total that exhausts direct research; default 75%% of context budget")
    init.add_argument("--branching-interval", type=int, default=5, help="minimum direct research actions between R5 attempts while living nodes exist")
    init.add_argument("--max-children", type=int, default=3)
    init.add_argument("--glossary-token-budget", type=int, default=3200, help="conservative UTF-8 byte/token upper bound for R1 glossary context")
    init.add_argument("--glossary-limit", type=int, default=12, help="maximum terms supplied to R1 (1..15)")
    run = sub.add_parser("research-run")
    for command in (init, run):
        command.add_argument("--script", help="JSON fixture responses/provider results for deterministic testing")
        command.add_argument("--llm-url", help="model URL (or MIRA_LLM_URL; default localhost:8090)")
        command.add_argument("--model", help="model identifier (or MIRA_LLM_MODEL; discover a single served model)")
        command.add_argument("--api-key-env", default="MIRA_LLM_API_KEY")
        command.add_argument("--temperature", type=float, default=0)
        command.add_argument("--max-tokens", type=int, default=2048)
        command.add_argument("--timeout", type=float, default=120)
        command.add_argument("--no-thinking", action="store_true", help="Qwen enable_thinking=false")
        command.add_argument("--plain-output", action="store_true", help="omit JSON response-format hint")
    run.add_argument("--control-term", action="append", default=[], help="literal term forbidden in the next R1 query; repeat for multiple terms")
    run.add_argument("--search-limit", type=int, default=2)
    run.add_argument("--max-cycles", type=int, default=20)
    run.add_argument("--acknowledge-interrupted", action="store_true")
    run.add_argument("--acknowledge-interrupted-searches", action="store_true", help="authorize another submission after inspecting uncertain retrieval_calls")
    demo = sub.add_parser("research-demo")
    demo.add_argument("--max-cycles", type=int, default=50)
    cleanup = sub.add_parser("research-cleanup", help="list experiments; delete explicitly selected, completed disposable experiments only with --apply")
    cleanup.add_argument("--experiment", action="append", default=[])
    cleanup.add_argument("--older-than-days", type=float)
    cleanup.add_argument("--apply", action="store_true")
    policy = cleanup.add_mutually_exclusive_group()
    policy.add_argument("--disposable", dest="retention", action="store_const", const="disposable", help="designate selected experiments disposable; this mode never deletes")
    policy.add_argument("--retain", dest="retention", action="store_const", const="retain", help="protect selected experiments from cleanup")
    state = sub.add_parser("research-state")
    glossary_export = sub.add_parser("glossary-export", help="regenerate research/glossary.md")
    glossary_rebuild = sub.add_parser("glossary-rebuild", help="rebuild the disposable glossary SQLite index")
    prune = sub.add_parser("research-prune")
    prune.add_argument("--apply", action="store_true", help="discard completed temporary retrievals; default dry run")
    viewer = sub.add_parser("viewer")
    viewer.add_argument("--port", type=int, default=8767)
    importer = sub.add_parser("research-import")
    importer.add_argument("source")
    importer.add_argument("--experiment", required=True)
    importer.add_argument("--transcript", help="optional existing exported transcript to preserve")
    show = sub.add_parser("transcript")
    show.add_argument("--full", action="store_true")
    show.add_argument("--concise", action="store_true")
    show.add_argument("--output", help="optional export path; catalog runs also export under memory/transcripts/")
    for command in (init, run, demo, state, show, prune, glossary_export, glossary_rebuild):
        command.add_argument("--experiment", help="persistent experiment name")


def execute(args):
    if args.command == "research-init":
        require((args.question is not None) != (args.question_file is not None),
                "provide a question or --question-file, but not both")
        if args.question_file is not None:
            from .questions import read
            read(args.question_file)  # Validate before creating an experiment or contacting the model.
    catalog = Experiments(args.memory_dir)
    if args.command == "research-cleanup":
        require(not args.root, "cleanup operates only within --memory-dir, not --root")
        return catalog.cleanup(args.experiment, apply=args.apply, older_than_days=args.older_than_days, retention=args.retention)
    if args.command == "research-import":
        require(not args.root, "research-import selects destination with --experiment, not --root")
        destination = catalog.import_run(args.source, args.experiment, transcript=args.transcript)
        for full in (False, True):
            catalog.export_transcript(args.experiment, transcript(destination, full=full), full=full)
        return {"experiment": args.experiment, "root": str(destination), "source_preserved": True}
    require(not (args.root and args.experiment), "choose --root or --experiment")
    managed = args.root is None
    if managed:
        path = catalog.create(args.experiment, disposable=args.command == "research-demo" or getattr(args, "disposable", False)) if args.command in {"research-init", "research-demo"} else catalog.select(args.experiment)
        args.root = str(path)
        args.experiment = path.name
    if args.command in {"research-init", "research-run", "research-demo"}:
        from .interactions import Interactions, configured_secrets
        from .live import LiveStore
        import os
        trace = Interactions(LiveStore(args.root), configured_secrets([os.environ.get(getattr(args, "api_key_env", "MIRA_LLM_API_KEY"), "")]))
        directory = catalog.home / "run-logs" if managed or args.memory_dir else None
        with trace.execution(directory, command=args.command) as log:
            result = _execute(args, catalog, managed, trace)
            log.reason = result.get("status", "initialized")
            return {**result, "execution_log": str(log.path)}
    return _execute(args, catalog, managed)


def _execute(args, catalog, managed, trace=None):
    if args.command == "research-demo":
        from .research_demo import demonstrate
        result = demonstrate(args.root, max_cycles=args.max_cycles, trace=trace)
        _tag_explicit_root(args, managed, disposable=True)
        if managed:
            for full in (False, True): catalog.export_transcript(args.experiment, transcript(args.root, full=full), full=full)
        return result
    if args.command == "transcript":
        full = args.full and not args.concise
        result = transcript(args.root, full=full)
        if managed: catalog.export_transcript(args.experiment, result, full=full)
        if args.output:
            from .experiments import atomic_text
            atomic_text(Path(args.output), result)
        return result
    if args.command in {"research-init", "research-run"}:
        require(not (args.script and args.llm_url), "choose --script or --llm-url")
        if args.script:
            script = loads(Path(args.script).read_text())
            llm = ScriptedLLM(script["responses"])
            adapters = {key: FixtureSearch(rows) for key, rows in script.get("providers", {}).items()}
        else:
            import os
            from .clients import HTTPModel
            from .providers import adapters as make_adapters
            endpoint = args.llm_url or os.environ.get("MIRA_LLM_URL", "http://127.0.0.1:8090")
            model = args.model or os.environ.get("MIRA_LLM_MODEL")
            if not model:
                from urllib.request import Request, urlopen
                headers = {}
                if os.environ.get(args.api_key_env): headers["Authorization"] = "Bearer " + os.environ[args.api_key_env]
                url = endpoint.rstrip("/") + ("/models" if endpoint.rstrip("/").endswith("/v1") else "/v1/models")
                with urlopen(Request(url, headers=headers), timeout=args.timeout) as response:
                    served = loads(response.read().decode())["data"]
                require(len(served) == 1, "specify --model when multiple models are served")
                model = served[0]["id"]
            llm = HTTPModel(endpoint, model, api_key=os.environ.get(args.api_key_env),
                temperature=args.temperature, max_tokens=args.max_tokens, timeout=args.timeout,
                no_thinking=args.no_thinking, json_output=not args.plain_output)
            adapters = make_adapters(limit=getattr(args,"search_limit",2))
    else:
        llm, adapters = ScriptedLLM([]), {}
    research = Research(args.root, llm, adapters, control_terms=getattr(args, "control_term", []))
    if trace is not None:
        trace.secrets = tuple(dict.fromkeys([*trace.secrets, *research.trace.secrets]))
        trace.log.secrets = trace.secrets
        trace.log.configure(llm.model, llm.settings)
        research.trace = trace
    if args.command == "research-init":
        result = research.initialize(args.question, args.database, question_file=args.question_file, synthesis_interval=args.synthesis_interval,
            context_budget=args.context_budget, output_reserve=args.output_reserve,
            strategy=args.strategy, registry=args.strategies, profile_registry=args.query_profiles,
            research_capacity_tokens=args.research_capacity_tokens, branching_interval=args.branching_interval,
            max_children=args.max_children, synthesis_output_reserve=args.synthesis_output_reserve,
            glossary_token_budget=args.glossary_token_budget, glossary_limit=args.glossary_limit)
        _tag_explicit_root(args, managed, disposable=args.disposable)
        return {**result, "storage_root": args.root, "experiment": args.experiment}
    if args.command == "research-state": return research.inspect()
    if args.command == "research-prune": return research.prune_retrievals(apply=args.apply)
    if args.command in {"glossary-export", "glossary-rebuild"}:
        with research.store.lock():
            research.store.read()
            state = loads(research.store._files()["research/state.json"])
            if args.command == "glossary-export": return research.glossary.export(state)
            research.glossary.ensure(state, rebuild=True)
            return {"path": str(research.glossary.path), "rebuilt": True}
    if args.acknowledge_interrupted: research.acknowledge_interrupted()
    if args.acknowledge_interrupted_searches: research.acknowledge_interrupted_searches()
    return research.run(args.max_cycles)


def _tag_explicit_root(args, managed, *, disposable):
    if managed: return
    from .experiments import atomic_text
    from .interactions import now
    atomic_text(Path(args.root).absolute() / "experiment.json", dumps({"version": 1,
        "created_at": now(), "retention": "disposable" if disposable else "retain"}))

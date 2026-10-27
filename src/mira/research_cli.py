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
    init.add_argument("question")
    init.add_argument("--database", action="append", required=True)
    init.add_argument("--synthesis-interval", type=int, default=5)
    init.add_argument("--context-budget", type=int, default=8192)
    init.add_argument("--output-reserve", type=int, default=2048)
    init.add_argument("--research-capacity-tokens", type=int, help="R5 estimated total that exhausts direct research; default 75%% of context budget")
    init.add_argument("--branching-interval", type=int, default=5, help="minimum direct research actions between R5 attempts while living nodes exist")
    init.add_argument("--max-children", type=int, default=3)
    run = sub.add_parser("research-run")
    run.add_argument("--script", help="JSON with responses and provider fixtures")
    run.add_argument("--llm-url", help="HTTP model base URL; credentials must use environment variable")
    run.add_argument("--model", help="model identifier reported by /v1/models")
    run.add_argument("--api-key-env", default="MIRA_LLM_API_KEY")
    run.add_argument("--temperature", type=float, default=0)
    run.add_argument("--max-tokens", type=int, default=2048)
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--no-thinking", action="store_true", help="llama.cpp/Qwen enable_thinking=false")
    run.add_argument("--plain-output", action="store_true", help="omit JSON response-format hint")
    run.add_argument("--control-term", action="append", default=[], help="literal term forbidden in the next R1 query; repeat for multiple terms")
    run.add_argument("--search-limit", type=int, default=2)
    run.add_argument("--max-cycles", type=int, default=20)
    run.add_argument("--acknowledge-interrupted", action="store_true")
    demo = sub.add_parser("research-demo")
    demo.add_argument("--max-cycles", type=int, default=50)
    state = sub.add_parser("research-state")
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
    for command in (init, run, demo, state, show):
        command.add_argument("--experiment", help="persistent experiment name")


def execute(args):
    catalog = Experiments(args.memory_dir)
    if args.command == "research-import":
        require(not args.root, "research-import selects destination with --experiment, not --root")
        destination = catalog.import_run(args.source, args.experiment, transcript=args.transcript)
        for full in (False, True):
            catalog.export_transcript(args.experiment, transcript(destination, full=full), full=full)
        return {"experiment": args.experiment, "root": str(destination), "source_preserved": True}
    require(not (args.root and args.experiment), "choose --root or --experiment")
    managed = args.root is None
    if managed:
        path = catalog.create(args.experiment) if args.command in {"research-init", "research-demo"} else catalog.select(args.experiment)
        args.root = str(path)
        args.experiment = path.name
    if args.command == "research-demo":
        from .research_demo import demonstrate
        result = demonstrate(args.root, max_cycles=args.max_cycles)
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
    if args.command == "research-run":
        require(bool(args.script) != bool(args.llm_url), "choose --script or --llm-url")
        if args.script:
            script = loads(Path(args.script).read_text())
            llm = ScriptedLLM(script["responses"])
            adapters = {key: FixtureSearch(rows) for key, rows in script["providers"].items()}
        else:
            import os
            from .clients import HTTPModel
            from .search import ArxivSearch
            llm = HTTPModel(args.llm_url, args.model, api_key=os.environ.get(args.api_key_env),
                temperature=args.temperature, max_tokens=args.max_tokens, timeout=args.timeout,
                no_thinking=args.no_thinking, json_output=not args.plain_output)
            adapters = {"arxiv": ArxivSearch(limit=args.search_limit)}
    else:
        llm, adapters = ScriptedLLM([]), {}
    research = Research(args.root, llm, adapters, control_terms=getattr(args, "control_term", []))
    if args.command == "research-init":
        result = research.initialize(args.question, args.database, synthesis_interval=args.synthesis_interval,
            context_budget=args.context_budget, output_reserve=args.output_reserve,
            research_capacity_tokens=args.research_capacity_tokens, branching_interval=args.branching_interval,
            max_children=args.max_children)
        return {**result, "storage_root": args.root, "experiment": args.experiment}
    if args.command == "research-state": return research.inspect()
    if args.acknowledge_interrupted: research.acknowledge_interrupted()
    return research.run(args.max_cycles)

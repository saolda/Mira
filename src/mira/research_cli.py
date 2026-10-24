"""Research CLI. Transcript reads independent records without opening a corpus."""
from pathlib import Path

from .format import dumps, loads
from .interactions import transcript
from .research import Research
from .decisions import ScriptedLLM
from .search import FixtureSearch


def register(sub):
    init = sub.add_parser("research-init")
    init.add_argument("question")
    init.add_argument("--database", action="append", required=True)
    init.add_argument("--synthesis-interval", type=int, default=5)
    init.add_argument("--context-budget", type=int, default=8192)
    init.add_argument("--output-reserve", type=int, default=2048)
    run = sub.add_parser("research-run")
    run.add_argument("--script", required=True, help="JSON with responses and provider fixtures")
    run.add_argument("--max-cycles", type=int, default=20)
    run.add_argument("--acknowledge-interrupted", action="store_true")
    sub.add_parser("research-state")
    show = sub.add_parser("transcript")
    show.add_argument("--full", action="store_true")
    show.add_argument("--concise", action="store_true")


def execute(args):
    if args.command == "transcript":
        return transcript(args.root, full=args.full and not args.concise)
    if args.command == "research-run":
        script = loads(Path(args.script).read_text())
        llm = ScriptedLLM(script["responses"])
        adapters = {key: FixtureSearch(rows) for key, rows in script["providers"].items()}
    else:
        llm, adapters = ScriptedLLM([]), {}
    research = Research(args.root, llm, adapters)
    if args.command == "research-init":
        return research.initialize(args.question, args.database, synthesis_interval=args.synthesis_interval,
            context_budget=args.context_budget, output_reserve=args.output_reserve)
    if args.command == "research-state": return research.inspect()
    if args.acknowledge_interrupted: research.acknowledge_interrupted()
    return research.run(args.max_cycles)

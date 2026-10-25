"""One real R3 call on a retrieved arXiv abstract, through the normal commit path."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from mira.clients import HTTPModel
from mira.experiments import Experiments
from mira.format import dumps, loads
from mira.interactions import read_records, transcript
from mira.research import Research
from mira.search import ArxivSearch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8090")
    parser.add_argument("--query", default="id:1512.05287")
    parser.add_argument("--question", default="What theoretical justification, empirical results and limitations are reported for dropout in recurrent neural networks?")
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    with urlopen(args.endpoint.rstrip("/") + "/v1/models", timeout=5) as response:
        model = json.load(response)["data"][0]["id"]
    catalog = Experiments()
    root = catalog.create(args.experiment)
    llm = HTTPModel(args.endpoint, model, max_tokens=2000, timeout=90, no_thinking=True)
    runner = Research(root, llm, {"arxiv": ArxivSearch(limit=1, timeout=30, max_abstract_chars=5000)})
    runner.initialize(args.question, ["arxiv"], context_budget=24000, output_reserve=2048)
    # Operator-provided exact-ID query skips R1. Neither R4 nor S2 is called.
    with runner.store.lock():
        token, memories, equations, ledger = runner.store.read()
        state = loads(runner.store._files()["research/state.json"])
        state["nodes"]["q1"]["keywords"] = [args.query]
        runner.store.publish(memories, equations, ledger, token, files={"research/state.json": dumps(state)}, operation_type="operator_query")
    search = runner.step()
    if search.get("search_status") != "ok":
        raise RuntimeError("Real research retrieval did not succeed: " + dumps(search))
    outcome = runner.step()
    records = read_records(root)
    markdown = [p.read_text() for p in sorted((root / "memories").glob("*.md"))]
    retrieved = [loads(p.read_text()) for p in sorted((root / "research/results").glob("*.json"))]
    report = {"experiment": args.experiment, "model": model, "research": retrieved,
              "calls": records, "outcome": outcome, "generated_markdown": markdown,
              "limitations": "One abstract; structural validation is not verification of scientific claims. No image downloads or symbolic mathematics."}
    (root / "r3_evaluation.json").write_text(dumps(report))
    for full in (False, True): catalog.export_transcript(args.experiment, transcript(root, full=full), full=full)
    if args.artifact: args.artifact.write_text(dumps(report))
    print(dumps({"experiment": args.experiment, "status": outcome["status"], "documents": len(markdown),
                 "validation": records[-1].get("validation"), "knowledge": runner.knowledge.validate()}), flush=True)


if __name__ == "__main__": main()

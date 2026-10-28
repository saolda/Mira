# Mira autonomous research endurance test — 28 October 2026

**Outcome:** The full 40-minute run completed with intact persistence, five research memories and two syntheses, but sustained autonomy failed: a repeated R3 schema rejection prevented further progress after roughly 2 minutes 19 seconds.

## Reproduction and preserved results

- Host: **Fractal**. Experiment: `autonomous-research-40min-20261028-attribution`.
- Question: “What techniques enable autonomous AI agents to conduct sustained, evidence-based scientific research, and what are their demonstrated strengths and limitations?”
- Code: `be11c10`, plus the owner's current uncommitted R3 additions for nonredundant extraction and author attribution. R3 SHA-256: `5364e4bc41080593398d3fdc8781d52102971e88175e9c3322f5ee5dea154489`, identical across all 79 R3 calls. Exact code/prompt hashes and prompt text are preserved locally.
- Local Qwen `Qwen3.6-35B-A3B-Q4_K_M.gguf`, llama.cpp `b1-091b6a7`, `http://127.0.0.1:8090`: **16,384 active context tokens per slot**, two slots, verified through server properties/slots. Native chat-template/tokenizer accounting; temperature 0, thinking disabled, JSON output, 4,096 output tokens/reserve, 180-second timeout.
- R0 selected **engineering**: arXiv → Crossref → OpenAlex → Wikipedia. Defaults retained: capacity 12,288 tokens (75% including reserve), branching/synthesis intervals 5, maximum 3 children, search limit 2. No reduced context or forced exhaustion.
- Preflight: **203 automated tests passed** (`PYTHONPATH=src python3 -m unittest discover -s tests -v`).

Full results: `/home/eric/Dev/Mira/memory/research/autonomous-research-40min-20261028-attribution/` (state, source payloads, memories, interactions, events, journals). Evaluation records: `endurance-run.json`, `endurance-analysis.json`, `endurance-quality-metrics.json`, `endurance-integrity-audit.json`; reproduction records: `endurance-baseline.json`, `endurance-supervisor.py`, `server-properties.json`, `automated-tests.log`.

Transcripts: `/home/eric/Dev/Mira/memory/transcripts/autonomous-research-40min-20261028-attribution/{concise,full}.md`. Only this report is committed.

## Execution and progress

- **Runtime:** 2,400.24 seconds; 18:37:39–19:17:39 AEDT (07:37:39–08:17:39 UTC), 28 October. Graceful wall-clock stop.
- **Work:** 86 cycle attempts, 13 committed (11 research + 2 synthesis), 73 rejected. R0 initialization is additional. **83 LLM calls:** R0 ×1, R1 ×1, R3 ×79, S2 ×2; 10 accepted and 73 rejected responses. R2 ×4 uses no model. No R4 or R5 calls.
- **Errors:** all 73 rejections are `empty extraction requires empty summary` on the same Wikipedia source, with two response-body variants. Zero JSON syntax failures, output truncations, HTTP/provider failures, context-budget failures, or supervisor exceptions; all 83 completions ended with `stop`. There were 72 reattempts after the initial failure; no R4 retry decision occurred.

| Provider, in search order | Searches | Retrieved | Accepted unique | Processed | Memories |
|---|---:|---:|---:|---:|---:|
| arXiv | 1 | 2 | 2 | 2 | 2 |
| Crossref | 1 | 2 | 2 | 2 | 1 |
| OpenAlex | 1 | 2 | 2 | 2 | 2 |
| Wikipedia | 1 | 2 | 2 | 0 | 0 |
| **Total** | **4** | **8** | **8** | **6** | **5** |

“Accepted” means retained after deduplication, not scientifically validated. All searches returned `ok`, with no duplicates. One processed source yielded an empty extraction. Both Wikipedia sources remain pending; the complete database sequence was searched, but the round never reached R4.

| Research memory | Source | Knowledge units | Approximate tokens |
|---|---|---:|---:|
| r1 | Agentic logistics/MCP | 6 | 794 |
| r2 | ReasFlow | 5 | 795 |
| r3 | TRACE runtime correction | 5 | 787 |
| r4 | Autonomous-agent review | 7 | 864 |
| r5 | Conceptual research framework | 6 | 845 |
| **Total** | | **29** | **4,085** |

Sizes use Qwen's tokenizer on canonical Markdown, excluding chat overhead/reserves. Median research memory: 795 tokens; summaries: 53–76 words. Synthesis memories `s1` and `s2` contain 4/5 units and 1,980/2,917 tokens respectively.

**Tree/capacity:** one living root, depth 0, no children, exhaustion transitions or R5 attempts. Its complete R5 request measures 8,701 tokens including reserve, below the unchanged 12,288 threshold. Pending evidence also prevents exhaustion. Rejections roll back scheduling counters, preventing later R4/synthesis opportunities. Branching quality was not exercised.

**S1/S2:** two selection passes, recorded inside S2 events at cycles 6 and 12; both selected complete collections, without condensed fallback representations, omissions or deferrals. There were no standalone S1 actions or rejected S2 calls. Request totals including output reserve were 6,693 and 9,880 tokens, within the 16,384 window. The latter serialized request was 24,794 bytes, illustrating why byte counts should not be treated as model tokens.

The external supervisor repeatedly calls unchanged `Research.step()`, including after failures, with retry delays capped at 30 seconds. It neither edits state nor bypasses validation or scheduling. At 40 minutes it stops dispatching and lets any active action finish.

## Quality and representative examples

**Successful R3 (interaction `00000004-*`):** `r2` separates ReasFlow from the logistics source. Its summary says “Authors report that ReasFlow autonomously generated five complete research papers,” qualifying scores as self-reported and domain/rubric-specific. The achievement unit is a `Claim`, improving on the previous unqualified wording.

**Remaining R3 attribution weakness:** `r3`, the TRACE abstract (`10.2139/ssrn.6759126`), summarizes the framework as enhancing reliability and significantly outperforming baselines, without making author attribution explicit in the summary. Its unit qualifications acknowledge the authors' simulated benchmark. Several assessments/proposals in `r1`, `r2`, and `r4` remain labelled `Finding`; qualification-level attribution does not establish independent verification.

**Valid empty R3 (interaction `00000006-*`):** Crossref's “Building Autonomous AI Agents for Scientific Research” (`10.61700/jbn2c5tcpv93w2419`) produced `{"summary":"","results":[]}` and was marked processed without allocating a memory.

**Unsuccessful R3 (first interaction `00000011-*`):** Wikipedia's “AI agent” (`wikipedia:en:78823217`) yielded no useful scientific-research results, but Qwen returned a nonempty descriptive summary with `results: []`. Valid JSON was rejected with `empty extraction requires empty summary`. Repeated rejection leaves state/pending evidence unchanged, also preventing extraction of the second result, “Claude (AI).”

**Successful synthesis (interactions `00000005-*`, `00000010-*`):** `s1` integrates `r1` and `r2`, contrasting external tool orchestration for logistics with internal verification and human supervision for mathematics. `s1#f3` explicitly identifies missing independent metrics and self-reported abstract-level demonstrations. `s2` then integrates `s1`, TRACE (`r3`), a review (`r4`), and a conceptual multi-agent proposal (`r5`), distinguishing simulated benchmark evidence from conceptual claims. Both syntheses retain stable unit references and canonical lineage.

**Synthesis shortcomings:** `s2#f1` elevates two examples into “two primary paradigms,” an unsupported general taxonomy. `s2#f2` reproduces the TRACE benchmark numbers but its prose implies demonstrated reliability more strongly than author-reported simulated evidence warrants. These are semantic shortcomings in accepted syntheses, not rejected S2 calls. Neither synthesis independently verifies the papers or establishes long-duration performance.

## Comparison and assessment

The previous `autonomous-research-40min` experiment stopped after **112.54 seconds**, with 17 normally committed cycles plus a recorded blocked S1 selection, three research memories, seven nodes and no S2 generation. Its byte-based context accounting stopped synthesis with `no_fitting_pair`. This run reached all four providers and completed S2 twice; its stall has a different cause. This is not a controlled comparison: code, memory format, prompt and output budget differ.

**Persistence/recovery:** validation passed for 7 documents, 38 knowledge units and 61 resolved relationships. All units resolve provenance, including synthesis lineage/derived origins; all four source payloads pass hash/descriptor checks. All 87 journal operations are committed, with no incomplete operations, orphans or unresolved calls. Rebuilt indexes pass integrity checks (45 records, 61 relationships). No crash/repair occurred; live crash recovery was not exercised beyond preflight tests. Hashes confirm the previous experiment, code, prompts and root documentation remained unchanged.

**Assessment:** early research meaningfully identified and compared tool orchestration, retrieval/memory, verification, human supervision and runtime correction. Abstracts and author-reported/simulated results still fall short of independently verified, sustained scientific discovery. Nearly all subsequent runtime repeated one schema failure. The priority follow-up is a bounded, auditable validation-failure policy that permits other work to proceed; no policy or prompt fix was introduced during this test.

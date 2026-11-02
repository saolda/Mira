# Production knowledge-unit synthesis validation

Date: 2026-11-02, Australia/Hobart. Worktree: `/home/eric/Dev/Mira`; branch: `main`.
Baseline: `bf95f8e`, synchronized from `origin/main`, including the committed synthesis experiment and provisional glossary implementation.

Implementation: `c498fde914969c2c755066ffa3b4d399efb38e51`.
Tests and validation harness: `c87a66ac78737e0f23529656da9f90a7d1afc1f6`.

## Executive assessment

The normal production `Research.step()` controller now supports deterministic S1 discovery, S2 opportunity planning and independently queued S3 execution. S1 makes **zero generation calls**; S2 and S3 each make at most one. Successful S3 publication, exact contributing-unit lineage and objective completion share one journal transaction. Contributing memories are retained unchanged.

Real Nomic/Qwen validation completed S1 → S2 → S3 on a clearly identified artificial measurement fixture. The published conditional result, **8 J − 4 J = +4 J; 8 J / 4 J = 2**, follows from its supplied premises. It explicitly rejects interpreting the inputs as independent empirical studies. This demonstrates the production workflow, **not new empirical scientific knowledge**.

Three bounded medical validation passes produced **15 S2 `no_candidate` evaluations and no medical synthesis**. The final pass found cross-branch finding groups, but Qwen often demanded evidence answering the entire root question instead of considering narrower analytical objectives. Some rejection reasons contain incorrect inequality reasoning. A separate geometric fixture exposed a serious wrong-operation error despite arithmetically consistent output. Structural checks, provenance and declared arithmetic do not establish scientific truth.

The active medical corpus, private inputs, earlier logs, glossary implementation, research prompts and diagnostic experiment were preserved. All live checks used disposable `/tmp/` corpora. No literature search, R1–R5 research action or destructive reset was run against the active corpus.

## Implemented production components

- **Discovery:** `synthesis_discovery.py` projects complete scientific unit fields, qualifications, types, relationships, original source identities and transitive leaf-unit lineage. Versions exclude memory-consumption/revision bookkeeping. Sparse lexical similarity, actual semantic vectors and explicit relationships produce bounded neighbourhoods and related pairs. Groups overlap and cross branches; ordering and ties are deterministic for fixed inputs/vectors.
- **Embeddings:** production research accepts the existing Nomic backend through `--embedding-url`/`--model-identity`, corresponding environment variables, or the Python constructor. A safely confined, disposable `synthesis.sqlite3` cache keys vectors by representation, configured model identity and scientific-content version. Changing the configured backend reopens discovery without replaying completed unit sets. Token-hashing fixtures are explicitly lexical-only, and service/cache failure reports degraded capability.
- **Evidence selection:** findings, equations and images form the primary neighbourhood. Bounded parent open questions remain contextual guidance. Question-only groups are not dispatched as evidence. The selected full unit contents, parent context, duplicate/relationship annotations, rationale, versions and downstream budget requirements are durable.
- **S2 planning:** one group, at most three objectives, independently validated. Exact supplied references, at least two parent memories, limitations and novelty rationale are required. A valid `no_candidate` completes evaluation. Invalid entries do not discard other valid objectives; an entirely invalid proposal set is a durable validation failure.
- **S3 execution:** one accepted objective per action; `synthesis` or `no_synthesis`. One to four substantive findings each identify actual contributions from at least two selected parent memories, literal attributed quotations, explanation, qualification and inference/hypothesis type. Declared arithmetic is checked against quoted operands, including signs, inequalities and relative precision for small quantities. All findings remain unverified.
- **Novelty:** S3 compares against selected inputs and bounded relevant existing knowledge. Already supplied inputs are referenced without duplicating their prompt text. The publication guard rejects repeated qualified propositions with contained leaf evidence and explicitly reviewed equivalence under the same evidence. Uncertain semantic similarity does not silently veto a result; additional evidence is retained. Similarity alone never merges or deletes units.
- **Participation:** new compact synthesis Markdown records exact `SYNTHESIZES` edges and contributing unit versions, sources and objective identity. Only accepted S3 references establish participation. Unused S1/S2 inputs are not marked as contributors. Original memories receive no consumption mark. Source/ancestry cycles are rejected; historical consumed memories and legacy formats remain readable.
- **Scheduling and recovery:** the canonical `unit_synthesis` register stores selected/evaluated/failed groups and independently pending/completed/failed/context-blocked objectives. Unordered exact version sets and normalized objective identities prevent ordinary replay without blanket subset/superset exclusion. A bounded three-action synthesis burst yields to ready research or R5 work. Pending stages survive restart. Immutable interaction receipts retain dispatched/uncertain outcomes, which block automatic resubmission. Failed/context-blocked work is distinct from scientific rejection. Historical pending two-stage execution reports `blocked_legacy_synthesis` for review.
- **Inspection:** the viewer shows exact supplied scientific units, parent context and objectives, and distinguishes partial unit inclusion from supplying an entire memory. Historical prompt rendering and read-only safeguards remain intact. The retired `S1.txt` is not an active model action; historical helper APIs and the diagnostic experiment remain available as compatibility/reference material.

## Architecture and exact prompts

`architecture.md` already contained the desired S1–S3 design at the fetched baseline. It remains a direct system specification: question-tree research, cross-branch knowledge-unit synthesis, deterministic S1, planning S2, execution S3, participation without consumption, exact-set accounting and R5-only ripeness. The implementation adds precise register, cache/configuration, response-contract, arithmetic-check, cadence and recovery details. The compact synthesis example now includes qualification, epistemic type and unit lineage. R1 provisional definitions and glossary precedence remain specified. No migration task list or contradictory two-action production path was added; `futureWork.md` was not changed.

The complete, exact final templates are [S2.txt](../prompt_templates/S2.txt) and [S3.txt](../prompt_templates/S3.txt).

| Template | SHA-256 |
| --- | --- |
| S2 | `74c7d6181a512b1d09dbabbc79078df01fa573c40aa46ebf9aac929062fb0778` |
| S3 | `e9c3f5674569a49525d137c982bd8c67cc762a195d5ccdf126b973ee19a442ba` |

Both use verified template bindings and exact rendered-request budgeting. The 4,096-token output reserve was preserved in live validation. Complete selected scientific units are never silently shortened after selection to make a request fit.

## Automated verification

**490 tests passed; zero failures, errors or skips; 93.525 seconds.** JavaScript syntax checking also passed.

Final full-suite results are recorded in `log/knowledge-unit-synthesis-20261102/acceptance-tests.md` and accompanying stdout/stderr. Coverage includes deterministic groups and ties; real-backend cache identity/invalidation and explicit degradation; numerical/population/endpoint distinctions; exact duplicates and complementary/same-source findings; independent S2 validation; partial S3 participation; quotation attribution; arithmetic/sign/inequality errors; ambiguous novelty and corroboration; immutable completed registers; killed/cyclic ancestry; fair scheduling; new-backend reopening; legacy parsing; cache reset; read-only viewer scope; and all R1/glossary/MeSH regressions.

Forked recovery tests interrupt S1 selection, S2 planning and S3 publication at prepared/replacement/commit boundaries. Repeated repair restores exactly one result without generation. Separate S2/S3 dispatch interruptions remain uncertain and cannot silently retry. Historical pending execution stays preserved and blocked. Changed source provenance/ineligible units fail before model dispatch. Later action failure rolls back the proposed memory and allocator. Tests use disposable fixtures.

Legacy tests asserting S1 model calls, S2 publication, whole-memory consumption and subset exclusion were replaced with tests of the new contracts. Legacy canonical-format, historical-event and source-provenance compatibility coverage remains. Initial contract-test failures and an intermediate numeric-token punctuation failure were corrected; retained logs show those development failures rather than presenting every intermediate run as successful.

Commands:

```sh
PYTHONPATH=src python3 scripts/run_tests.py
node --check src/mira/viewer_assets/app.js
```

## Actual local-service verification

Services: Qwen `Qwen3.6-35B-A3B-Q4_K_M.gguf`, temperature 0, thinking disabled, JSON output, maximum output 4,096, native context 16,384. Nomic `nomic-embed-text-v1.5.Q5_K_M.gguf`, **768 dimensions**, `search_document: ` prefix; artifact SHA-256 `0c7930f6c4f6f29b7da5046e3a2c0832aa3f602db3de5760a95f0582dbd3d6e6`. These were real local services, not hashing test doubles. S1's embedding and tokenizer requests are distinct from generation calls.

[validate_unit_synthesis.py](../scripts/validate_unit_synthesis.py) copies journal-validated medical data without opening it for execution. Only disposable cadence counters are advanced so the actual controller exercises synthesis without searching or changing question statuses. The controller is restarted between stages. Full interaction requests, template snapshots, settings, responses, validation events, state and journals remain locally inspectable.

| Validation pass | Controller actions | Generation calls | Input / output tokens | Seconds | Observed outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Initial medical | 10 | 5 | 15,710 / 922 | 53.346 | Five `no_candidate`; question wording dominated discovery |
| Medical, requiring a finding in each group | 10 | 5 | 25,782 / 1,013 | 56.262 | Five `no_candidate`; mixed groups still dominated by gaps/questions |
| Final medical, primary scientific units | 10 | 5 | 20,626 / 996 | 53.537 | Five `no_candidate`; genuine cross-branch groups, no medical synthesis |
| Geometric doubling fixture | 3 | 2 | 3,933 / 1,386 | 30.179 | S2 idea; scientifically wrong S3 rejected on reference contract |
| Defined matched 4-J / 8-J fixture | 3 | 2 | 3,939 / 1,399 | 28.973 | S2 objective and source-attributed S3 publication |

These **19 generation calls** are separate development comparisons, not automatic retries of failed scientific responses. One earlier fixture setup failed before dispatch because its compact-memory label was invalid; the reproducer now tests canonical setup. The fixture snapshot-revision bookkeeping and cache-lock discipline were subsequently tightened without changing any generated scientific text.

### Medical findings and scientific review

The final five selected sets were:

1. `r3#f1`, `rc#e1`, `rc#f1` — growth categories and a benign-tumour report, spanning q1/q6.
2. `re#f1`, `re#f2`, `rg#f1`, `rg#f2`, `rg#f3` — morphology and PET findings, spanning q4/q6.
3. `r3#f1`, `r8#f1`, `rb#f2`, `rc#e1`, `rc#f1` — a mixed growth/invasiveness/other-site group, spanning four branches.
4. `r9#f1`, `rd#f1`, `rd#f2` — IgG4-related mimicry/diagnostic criteria across q3/q6.
5. `r9#f1`, `rd#f1` — a smaller overlapping mimicry comparison.

Maximum measured input plus reserve was **10,295 tokens**. Original research memories remained byte-identical in every medical copy. All five evaluated groups were recognized by the replay guard; ordinary changed/overlapping groups remain eligible.

**Observed:** no S2 objective, S3 medical call or medical finding was produced in these bounded passes. This is not corpus-wide exhaustion and does not prove no useful synthesis exists. The final model repeatedly rejected opportunities because they could not resolve four-week infection-versus-malignancy discrimination. That is a defensible reason not to answer the whole question, but does not itself rule out the narrower methodological comparisons permitted by S2.

**Observed reasoning failures:** a final rejection calls a `≤400-day` category “orders of magnitude slower” than 28 days and a `<600-day` bound “significantly slower.” Both bounds include 28 days; the defensible limitation is lack of a specific measured subgroup/comparison. The source corpus contains known extraction/qualification problems, and the model can amplify them. No source text or model output was silently corrected.

The earlier [synthesis-discovery experiment](synthesis-discovery-experiment.md), preserved at `6d717df595bad9`, evaluated six differently selected groups and proposed nine ideas from three groups. It established no genuine duplicates or S3 findings and documented endpoint/population errors. The present planning results do not demonstrate improvement over that experiment: group construction, prompt contract and context differ. Real embeddings and valid references remain insufficient measures of scientific productivity.

### Geometric fixture: failure retained

Defined premises were spherical geometry `V ∝ D³` and constant exponential volume growth doubling every 28 days. Qwen's S2 proposal prematurely predicted **9.33 days**, and S3 repeated that answer by choosing `28 / 3`. The declared division is arithmetically correct; the physical mapping is wrong. Diameter doubling requires eightfold volume, hence three volume-doubling intervals: **84 days** under those assumptions.

S3 was rejected because it supplied novelty comparisons to selected units omitted from the initial novelty list, **not because the harness proved the physics wrong**. The final contract explicitly includes selected conclusions in novelty review, avoiding that incidental reference rejection. There is no claim that final arithmetic validation would automatically catch this choice-of-operation error. This case demonstrates S2 answer contamination and the need for stronger scientific verification beyond quotations and scalar arithmetic.

### Matched-measurement fixture: limited success

The separate fixture defines initial energy 4 J and final energy 8 J under matched conditions. It explicitly supplies artificial premises from one fixture, not independent studies or medical observations. Qwen proposed a quantitative comparison and published one compact synthesis with +4 J change and ratio 2. Both declared calculations and supporting quotations pass the production checks. The qualification correctly excludes empirical estimates, independent replication and uncertainty intervals for these defined constants.

The output references exactly `r1#f1` and `r2#f1`; original memories remain unchanged. The completed S2 group is suppressed on replay. Outcome recovery dispatches no model calls, and full canonical validation succeeds. The maximum rendered input plus reserve was **6,449 tokens**. This is a checkable conditional deduction, not evidence of general scientific reasoning reliability or a new real-world discovery.

## Preservation, artifacts and limitations

A final audit checks **2,681 protected pre-existing paths**: active/legacy research, private files, research prompts, `futureWork.md` and the synthesis experiment files. It found **zero changes and zero new active-memory files**. Existing logs were preserved. `AGENTS.md` appeared as a user-created untracked file during this task and is preserved separately from these commits.

Ignored local artifacts are under `log/knowledge-unit-synthesis-20261102/`: full test logs; `protected-before.json`/`preservation-after.json`; and per-pass `result.json`, execution JSONL and stdout/stderr in `medical/`, `medical-findings/`, `medical-primary/`, `algebra/` and `matched-measurements/`. Each result records its disposable corpus path. The successful fixture remains at `/tmp/mira-production-synthesis-ikqr19rx/mathematical-fixture`; final medical copy at `/tmp/mira-production-synthesis-6ychnxrq/medical`. No private corpus, log or generated memory is committed.

Remaining limits:

- Scientific correctness, source independence, causal claims, applicability of arithmetic and semantic novelty are not decided by structural validation. The geometric failure is a concrete counterexample, not a hypothetical warning.
- S2 can overfocus on the root question and can inject a wrong anticipated answer into S3. Broader objective-quality and scientific-reasoning evaluation is needed before claiming better research outcomes.
- Similarity/category labels are conservative discovery annotations, not validated scientific equivalence classes. Exact-set suppression does not recognize every reworded objective; novelty comparison can miss paraphrases.
- Embeddings update incrementally, but exact neighbour scanning is still quadratic in comparisons. Bounded heaps avoid a durable quadratic matrix; large-corpus latency and independent retrieval benchmarks remain unvalidated. Backend recovery under the same identity may need an explicit future rediscovery operation or new knowledge.
- Historical pending execution and failed/context-blocked objectives require review; no automatic evidence repair or unsafe resubmission mechanism was added. Existing recovery safeguards remain authoritative.
- The preserved diagnostic script's old production-S1 control targets the historical two-stage prompt contract. It is not a current production entry point; its standalone discovery/evaluation functions and historical artifacts remain available.

Production integration is complete; the scientific evidence supports a working, traceable pipeline and one simple conditional deduction, **not improved medical conclusions or general scientific validity**.

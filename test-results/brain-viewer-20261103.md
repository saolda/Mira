# Mira Brain Viewer — implementation and active-corpus validation

Completed 2026-11-03 in `/home/eric/Dev/Mira`, branch `main`.

Mira's existing local viewer now provides **Research Overview**, **Knowledge Explorer** and **Knowledge Relationships**, alongside the original Decisions, human reviews, recorded model requests/responses and standard Glossary. The implementation makes no inference or source-provider calls, starts no research and writes no scientific state.

## Open the viewer

```bash
PYTHONPATH=src python3 -m mira viewer
```

Open <http://127.0.0.1:8767/>. The active corpus is selected by default; explicitly selected legacy experiments remain inspectable. No second server implementation was introduced. Browser verification used the same server on temporary port 18867.

## Implemented interface

- Overview: root and active research questions, recorded objectives/brief, strategy, root/active-node status, research and synthesis counters, snapshot identity, unit inventory, canonical question statuses, synthesis-stage activity and outstanding work.
- Explorer: every canonical unit, including historical branches and synthesis memories. Deterministic search covers IDs, labels, complete scientific fields, source titles/identifiers, parent memories and research questions. Type, origin, evidence, overlapping participation, branch/descendants and parent-memory filters combine. Six sorting choices and exact-count pagination are available; the default page is 50, with an API maximum of 200.
- Details: complete proposition, qualification and recorded fields; scientific content precedes technical bookkeeping. Original canonical memory, source metadata/links, retained hash-validated source text when available, equation expression/variables/units/assumptions, question state, scientific-validation records, synthesis objective, contributing units and versioned activity history remain inspectable.
- Question navigation: collapsed expandable hierarchy, direct/subtree unit counts, memories, synthesis memories and pending activity; branch and memory links clear unrelated filters to show their complete inventories. Selected units and expanded branches survive refresh.
- Relationships: a selected unit and up to 12 directly related units per graph page; directed arrows, type/status labels, keyboard-activatable nodes, clickable detail navigation, a complete edge table and original-source-unit ancestry. All edge counts are visible. Additional neighbours are paged rather than silently dropped.
- Native local assets only. Scientific strings use safe DOM text APIs; external source links allow HTTP/HTTPS without credentials. Existing host checks, CSP, review-token protection and path confinement remain in place.

## Reference studied

Inspected the local `saolda/autonomous_ai` checkout at commit `5fd6107`, including `src/brain_viewer.py`, `viewer/index.html`, `app.js`, `health.js`, `app.css` and `docs/brain_viewer_health.md`.

Adapted the useful separation of overview and detailed inspection, restrained summary cards, expandable hierarchy, searchable inventories, stable selection on refresh, explicit missing-data labels and read-only observability. No goal/cycle scientific model, service probes, progress percentages or source code were copied into Mira. Mira's canonical research questions, individual units and S1–S3 records remain the data model.

## Actual active corpus: observed facts

Experiment: `medical-retrieval-repair-20261031`. Strategy: `medical`. Root question:

> Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

Canonical revision: `65e248a831a23f6b3eb4f61e1bd03b1d20b1831b0d7e2c2ec84e1aae8834d3ee`. Research-state revision **251**. Active node **q6**, status **living**. Root node **q1**, status **split**. Recorded counters are **228 research cycles** and **18 synthesis cycles**. The latter is a persisted legacy activity counter; it does not establish 18 successful syntheses or 18 attempts of the current unit pipeline. No separate frozen objectives/brief are recorded for this corpus.

| Inventory | Count |
| --- | ---: |
| Research memories | 16 |
| Synthesis memories | 0 |
| Total knowledge units | 46 |
| Structural findings | 36 |
| Structural questions | 9 |
| Structural equations | 1 |
| Structural images | 0 |
| Synthesized units | 0 |

The separate scientific-type distribution is **30 findings, 5 claims, 1 inference, 9 questions and 1 equation**. Observation and hypothesis counts are zero. These are alternative classifications of the same 46 units, not quantities to add to structural counts. No unit was omitted or counted twice.

| Originating question | Direct units |
| --- | ---: |
| q1 | 19 |
| q3 | 5 |
| q4 | 10 |
| q6 | 12 |
| q2, q5, q7–q13 | 0 |

There are **9 living** and **4 split** research nodes; answered, exhausted and killed counts are zero. All **9 question units are open**, independently of their containing node statuses. All **46 units lack an explicit evidence-status field**, so the viewer displays **Status not recorded**; it does not certify them or silently add an evidence assessment.

The source inventory includes **81 processed sources**, including those producing no units; **16 source IDs** have research memories yielding units. This counts retained identifiers, not independently replicated studies. There are **47 projected edges**: one explicitly recorded `RELATED_TO` edge from `rc#e1` to `rc#f1`, and 46 inherited `CITES` attributions. Inherited citations are labelled as derived source attribution, not invented scientific relationships.

### Synthesis and outstanding work

The active corpus has no `unit_synthesis` register, no synthesis memories and no published `SYNTHESIZES` relationships. Unit-level S1 selection, S2 evaluation, S3 attempt/completion and failure counts therefore remain **Not recorded**. There is no reliable basis for attributing past unit-level selection to individual findings. No units are shown as contributing to a published synthesis; all 46 remain without such a recorded contribution. Nine open question units and nine living research branches remain visible.

Modern S1/S2/S3 behaviour, synthesized findings, multi-generation lineage, subset contributions, nonconsumptive reuse, blocked/failed processing and image units were demonstrated with deterministic temporary-corpus fixtures. These are test capabilities, not discoveries in the active medical corpus.

### Verified real examples

- `r1#f1`: source-derived finding on spiculation as a cancer predictor. Complete proposition, original cohort qualifications and PMID 24004118 source link match the canonical memory.
- `r1#q1`: recorded open question about comparative growth kinetics; its state is not replaced by the containing node's disposition.
- `rc#e1`: exact equation `TVDT = (t * ln(2)) / ln(V2/V1)`, original variable descriptions, recorded units and model-reported/unverified equation attribution.
- `rc#f1`: complete recorded pulmonary sclerosing pneumocytoma growth finding, including its retrospective, single-centre and small-sample qualifications. It is accessible from the actual equation's `RELATED_TO` edge.

Field-by-field comparisons and original-memory byte comparisons passed for all four examples. The complete 46-ID inventory was also compared with the canonical parser's units. No active example of a synthesized finding, a unit with modern synthesis history or an image exists; none was invented.

## Status and lineage rules

1. Origin follows the parent research/synthesis memory. Question-specific origin remains a separate recorded field.
2. Structural type follows the unit anchor. Scientific type uses recorded `Epistemic type`, then `Kind`, then structural type. A synthesized inference remains structurally a finding.
3. Evidence/validation uses actual recorded values. Missing status is missing; a structurally valid S3 publication is not independently scientifically verified.
4. Synthesis history is overlapping, versioned activity. S1 selected, S2 evaluated/objective/no-candidate, S3 attempted/completed/no-synthesis/failed/blocked and published contribution are separate classifications. Old-version events remain visible without marking a changed current version selected. An unknown contributing version remains explicitly unknown.
5. Actual publication participation comes from canonical `SYNTHESIZES` edges and recorded input versions, not an S1 group or all proposed inputs. A unit can contribute to multiple outputs and is not consumed.
6. Question-tree context uses recorded node status and eligible subtree. Historical knowledge stays visible; being outside an eligible subtree does not invalidate it. Controller-answered nodes do not automatically answer question units.

Original-source ancestry follows recorded synthesis edges across generations. It does not establish source independence or validate the inference. Invalid/missing targets and cyclic synthesis ancestry fail validation; the viewer does not repair scientific data.

## Structured APIs and future reporting foundation

All routes extend the existing server under `/api/experiments/<name>/`:

| Route | Projection |
| --- | --- |
| `overview` | Identity, counts, question tree, coverage and synthesis activity |
| `knowledge` | Searchable/filterable/sortable paginated inventory and exact totals |
| `knowledge/<encoded-unit-id>` | Complete unit, parent memory, evidence, objective and history |
| `relationships/<encoded-unit-id>` | Directed neighbourhood, edge statuses/provenance and leaf ancestry |
| `questions/<node-id>` | Direct/subtree unit and pending-work summary |
| `snapshot` | Versioned structured research-state export, independent of browser layout |

Encode `#` as `%23`. Schema **`mira.research-state/1`** includes stable IDs, canonical revision, research identity/objectives, question statuses, all units and fields, memory references, source inventory, available evidence, epistemic/validation dimensions, relationships, lineage, synthesis records/outcomes, outstanding questions and limitations. It contains no narrative scientific conclusions and introduces no paper-generation action.

Each response represents one locked, validated canonical snapshot. Pass `revision=<hash>` to require the same snapshot across requests; a mismatch returns **409**. An active writer or pending journal recovery returns **503**, with no stale-success fallback. Canonical corruption fails rather than being hidden by the cache. No arbitrary file-reading route was added.

A bounded in-memory cache reuses the validated projection keyed to canonical revision and file/journal/payload signatures. Subsequent interactions recheck locks and metadata without reparsing the full event history. Changes trigger the existing canonical reader and consistency checks. Cached data is disposable; no scientific database or canonical after-images are written.

## Validation and performance

- **611 automated tests passed**, zero failures/errors/skips, **132.841 seconds**. This includes all previous regressions plus **35 new knowledge-inspection tests**. No existing tests were removed for this task.
- Coverage includes all structural/scientific types, empty inventory, historical branches, S1/S2/S3 distinctions, no-synthesis/failure/blocking, actual subset contribution, nonconsumptive reuse, unit versions, source retention/hash failure, directed and multi-generation lineage, malformed targets, pagination/filter combinations, private-file exclusion, injection-safe rendering, snapshot invalidation, active writer and pending recovery.
- Real Chromium browser acceptance passed against the active corpus: overview/default selection, all 46 units, ID search, combined filters, full scientific qualifications, source links, open-question state, exact equation/units, focused graph/navigation, branch links, refresh selection/expansion, original R4 decision inputs, human-review panel and updated standard glossary. All resources and API requests remained local. Overview/explorer screenshots were visually inspected; private screenshots/logs remain ignored locally.
- Active-corpus cold validated projection: **0.332 s**. Median warm inventory request over five measurements: **0.072 s**. Deterministic 1,000-unit pure projection: **0.483 s**; pagination tests recovered every ID exactly once. These are local observations, not universal performance guarantees.
- Initial test-fixture defects were corrected before final validation; the final complete suite and browser run pass.

## Preservation, limitations and follow-up

Before/after hashes checked **3,472 existing memory files**: **zero changes, zero deletions, zero additions**. The entire active corpus, private inputs, source payloads, journal, research/synthesis state, glossary definitions and generated glossary views are unchanged. No new experiment was initialized. No real LLM or provider call occurred.

`architecture.md` and **all production prompts, including R1**, are unchanged against the start of this Brain Viewer task. The separately approved R1/glossary work is already in baseline commit `8b781e9`. No additional architecture or prompt change is required or proposed here.

Limits: refresh is explicit; large full snapshot exports remain proportional to corpus size, and cache invalidation still requires file-metadata checks. This is not a historical version browser, but historical participation versions are retained. Legacy unit-level synthesis data cannot be reconstructed reliably. Missing/pruned source text stays unavailable; a retrieved source abstract is labelled as such rather than fabricated as an exact unit-supporting quotation. Equations use readable exact text without an external math library; images expose recorded descriptions/references without fetching remote media. The browser acceptance script targets this medical validation corpus. No paper generation or scientific quality scoring was implemented.

## Commits

Implementation: `5a8ff6731e339cca866abe4a65f7bea50675da77`. Tests: `b492c83d2688f1e3b35004f9bda0ab0f90e13af2`. This completion report and the ordinary latest test report are committed separately. All three commits are then pushed to `origin/main` and remote synchronization verified in the completion response. Private research data, generated research snapshots, screenshots and execution logs are not committed.

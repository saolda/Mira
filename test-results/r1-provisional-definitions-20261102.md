# R1 provisional glossary definitions

Date: 2026-11-02. Repository/worktree: `/home/eric/Dev/Mira`, branch `main`. Baseline: `6d717df595bad92dc129a2a1d1b717e7197e4afe`, synchronized with `origin/main` before implementation.

## Assessment

R1 can now append up to three provisional definitions for existing, supplied glossary entries during its existing search-planning call. Definition admission, contextual preference and provenance live in a separate glossary module; production synthesis selection and execution are unchanged. Independently invalid definitions do not discard valid searches. Definitions publish in the same durable R1 transaction, and remain eligible for later MeSH enrichment.

**477 tests passed**, with no failures, errors or skips, in **60.143 seconds**. A disposable local-Qwen check admitted three definitions, supplied them to the next R1 call without regeneration, and abstained on an unexpanded, domain-unspecified abbreviation. Search selections changed and token costs increased. This small test does **not** establish improved search quality or reliable scientific correctness: one generated qualification incorrectly conflates volume and diameter doubling times.

## Implementation and canonical schema

The optional response field is `provisional_definitions`, containing objects with exactly `term_id`, `definition`, `scope` and `ambiguity`. Legacy R1 responses without it remain accepted. Admission requires an actual supplied `g*` ID and `definition_eligible=true`. The first three proposals are considered; additional entries, duplicates, unknown/unsupplied IDs, malformed values, authority/confidence fields, obvious citation strings and explicit unresolved-meaning statements are rejected independently. Definition, scope and ambiguity limits are 600, 160 and 400 characters respectively. These checks enforce the contract; they do not verify scientific truth.

Canonical glossary records retain their existing identity, evidence, relationships and append-only definitions. A model row adds:

```json
{
  "origin": "llm_generated",
  "verification": "provisional",
  "term_id": "g1",
  "text": "…",
  "scope": "…",
  "ambiguity": "…",
  "model": "actual configured model identity",
  "interaction_ref": "interactions/<sequence>-<event-id>/request.json",
  "event_ref": "events/<event-id>.json",
  "template_sha256": "…",
  "request_sha256": "…",
  "context": {"node_id": "q1", "question": "…"}
}
```

There is no fabricated source evidence or authority record. Model-only availability has status `provisional`; existing `source_defined` and `multiple_definitions` continue to describe independently sourced definitions. Legacy records remain valid. SQLite remains a disposable index with its existing schema; complete hash-validated canonical records supply definitions.

New model rows require a matching committed R1 event and accepted proposal. Glossary after-images and the search plan share the existing journal publication. An all-invalid search selection or later action failure publishes no model definitions. Crash recovery applies the prepared transaction without another model call. Newly discovered R1 concepts still enter only the existing unverified concept register, never a new glossary identity.

## Context, precedence and enrichment

Applicable definitions are ordered deterministically: authority, source-supported, then provisional, with stable text/content tie-breaking. All retained definitions remain visible in exports. A MeSH match without usable descriptive text does not count as a definition. A different contextual meaning can be excluded even when it has stronger provenance.

Applicability uses conservative lexical rules over the question, term names, scope, definition and locally relevant evidence passages. It is **not semantic disambiguation**: shared generic words can retain a wrong scope, and sparse or synonymous descriptions can miss a correct one. An unchanged/normalized question or overlapping contextual vocabulary retains an existing provisional definition; materially disjoint vocabulary can permit another scope. Short uncertain contexts conservatively retain the same node's definition. This suppresses routine regeneration without interpreting punctuation or another research round as a new meaning.

R1 keeps its bounded relevance selection and glossary budget. The projection supplies the preferred definition, availability flag and explicit provisional/authority metadata. Provisional definitions never complete the authoritative-enrichment backlog. Existing provider limits, cache, cooldowns and retry handling remain in force, including after a later source definition is appended. No terminology provider or invalidation interface was added. An approved explicit-invalidation workflow remains future work.

Markdown and HTML show model origin, provisional verification, scientific scope, ambiguity, model identity, interaction/event references and template provenance. Supporting passages establish the term's occurrence, not verification of a generated definition. Existing authority links, escaping, deterministic export, offline search and atomic writes remain supported.

## Final prompt and controlled verification

The exact final prompt is [R1.txt](../prompt_templates/R1.txt). It uses the supplied three-task replacement with two additions: obey `definition_eligible=true` and avoid same-scope regeneration; omit unexpanded/domain-unspecified abbreviations rather than list possible expansions. The seven template slots and 4,096-token output reserve are unchanged.

The first four-call development pass exposed both problems: Qwen proposed the same three definitions again (Python rejected them while committing valid searches), and supplied an APC expansion list instead of abstaining. That list included the questionable expansion “Annual Processing Charge” and was admitted by the initial structural validator. These outputs were retained. The final prompt clarifications and unresolved-meaning guard were then tested in a separate four-call pass. These are explicit development comparisons, not automatic failed-response retries.

Final settings: local port 8090; `Qwen3.6-35B-A3B-Q4_K_M.gguf`; 16,384-token context; temperature 0; thinking disabled; JSON output; maximum output/reserve 4,096. Seed terminology was **Volume doubling time, Spiculation and SUVmax**, mentioned without definitions in synthetic passages. Before/after starting contexts were identical; only R1's template differed. No literature provider or live MeSH calls occurred. The follow-up resets only the disposable fixture's search cursor to request another R1; it is not a complete research trajectory.

| Final-pass action | Input tokens | Output tokens | Seconds | Definition outcome |
| --- | ---: | ---: | ---: | --- |
| Old-template control | 814 | 173 | 3.533 | No DEFINE task |
| New template | 1,347 | 512 | 9.921 | Three admitted |
| Follow-up with stored definitions | 2,105 | 268 | 6.128 | No proposals; three retained |
| Ambiguous APC, no domain/expansion | 1,213 | 147 | 3.201 | Abstained; entry remains candidate |

Each action made exactly one generation call. Eight generation calls were made across the two development passes. Final rendered input plus output reserve was 4,910 tokens for the control, 5,443 for the new template, and at most 6,201 for the follow-up: all within 16,384. The paired new-template call used 533 more input tokens and 339 more output tokens; total tokens increased from 987 to 1,859 (88.3%).

Control searches were `Lung-RADS`, `PET/CT`, `CT volumetry`, `FDG uptake`, `malignancy probability`. New-template searches were `volume doubling time`, `spiculation`, `SUVmax`, `PET CT`, `pulmonary nodule`, `volumetry`. The follow-up received all three provisional definitions, recognized their ineligibility for regeneration, and selected `volumetric growth rate`, `PET CT fusion`, `nodule morphology`, `FDG uptake`. No retrieval comparison establishes which plan is better; adding DEFINE measurably changes planning and cost.

The definitions' core descriptions concern volume growth, spiky radiological margins and maximum standardized uptake value respectively. They are concise and relevant terminology guidance, not independent diagnostic evidence. Crucially, Qwen's volume-doubling ambiguity says it is “often used interchangeably with diameter doubling time.” That is misleading: under constant-shape exponential growth, volume is proportional to diameter cubed, so diameter doubling takes three volume-doubling intervals. The model's wording was preserved, not repaired. The spiculation association does not establish diagnostic specificity, and SUVmax lacks full normalization/measurement detail. No infection-versus-malignancy probability was estimated or validated.

## Tests and preservation

Twenty-one added tests cover admission and provenance, optional/legacy responses, independent component rejection, unsupplied IDs, duplicates/limits, uncertainty and scoped abbreviations, repeat suppression, source/authority precedence, empty MeSH descriptions, continued enrichment/cooldowns, concept-register separation, malformed JSON, rollback, escaping/exports, append-only records and four journal crash boundaries. Existing R1, glossary, terminology, recovery and synthesis tests also pass. The old prompt-example assertion was updated for the new JSON layout.

Run the full suite with `PYTHONPATH=src python3 scripts/run_tests.py`. The controlled check is reproducible with [validate_r1_definitions.py](../scripts/validate_r1_definitions.py), an explicit pre-change template and a fresh output directory. It always uses disposable `/tmp/` corpora.

The preservation audit compared **2,683 pre-existing paths**, including active/legacy memory, private inputs, protected architecture/future-work documents, other prompts and synthesis experiment files. **No protected changes or new memory files were found.** No active experiment was initialized, reset, resumed or exported. Only disposable glossaries were generated. Existing logs were preserved; new interactions, test logs and preservation snapshots are ignored under `log/r1-provisional-definitions-20261102/`, with the final controlled pass in `revised/`. Disposable corpora remain at `/tmp/mira-r1-definitions-he2xkc9a` and `/tmp/mira-r1-definitions-ofq7t5ux`.

## Preserved synthesis baseline

[The synthesis-discovery experiment](synthesis-discovery-experiment.md) is committed baseline `6d717df595bad9`. Its 36 finding-shaped units produced 33 groups. Hybrid retrieval found 12/16 reviewed relationships versus lexical retrieval's 8/16; one variant introduced a hard negative. No genuine duplicate was established. Six experimental S2 calls returned nine ideas from three groups and `no_candidate` for three; a production-template control also returned `no_candidate`. Endpoint/population errors, semantic redundancy and restated gaps prevented treating ideas as scientific progress. No S3 synthesis was demonstrated. Its full suite passed 456 tests.

Those experimental files and production synthesis behavior are preserved here. This is task modularity, not a decision against a later production S1–S3 redesign. Proposed documentation changes and follow-up limitations are recorded [separately for review](r1-provisional-definitions-architecture-proposals.md); `architecture.md` and `futureWork.md` were not edited.

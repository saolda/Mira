# Ordered R3 extraction and R1 heading controls

> Historical milestone report. The current R1–R5 contract, three-way R4,
> question provenance and branching/synthesis policies are documented in
> [architecture](../architecture.md) and [execution](research_execution.md).


R3 extracts research information. Python creates and manages memories. This
implementation keeps that boundary explicit: the model supplies one ordered array,
not memory drafts or permanent IDs. R4 is unchanged. The only S2 changes allow its
existing lineage field to reference equation/image anchors when an input has no
textual finding; no synthesis cadence, priority or disposition rules changed.

## R1 control terms

Python always supplies this initial list through the existing `control_terms` slot:

```python
CONTROL_TERMS = [
    "summary", "explanation", "findings", "proposition", "provenance",
    "evidence", "sources", "references", "metadata", "title",
]
```

The existing per-run explicit controls are additive. Comparisons are case-insensitive
whole-word/phrase matches, so `evidence` is removed but `evidential` is not.
Python removes prohibited words from otherwise useful components, normalizes
whitespace and trims empty punctuation. Empty components are dropped; if nothing
useful remains, the response is rejected and no query is dispatched. For example:
`["SUMMARY dropout", "evidence", "metadata uncertainty"]` becomes
`["dropout", "uncertainty"]`, joined by R2 into `dropout uncertainty`.
The raw model response is preserved; the action event records original and accepted
components under `keyword_filter`.

Previous R1 components still come from committed R1 event lists, in order with
duplicates removed. They remain a separate advisory variable, not a ban list.
Question deduplication and the sanitized R1 memory projection remain intact.

## Exact R3 input

Only three variables are declared and supplied:

- `question`: selected question in its original wording.
- `question_context`: the same root/ancestor whitespace-comparison deduplication
  used by R1, excluding the selected question and preserving first original wording.
- `research`: `{"status": ..., "results": [...]}` containing the supplied source
  rows unchanged. Source identifiers, titles, authors, publication information,
  URLs, content-kind/truncation flags, abstracts/excerpts, and any supplied equation
  or figure metadata are retained. No node IDs, query history, provider pointers,
  existing memories or batch file paths are sent. Raw provider feeds stay on disk.

The arXiv adapter additionally retains available updated dates, links, publication
comments, journal references and DOIs. Missing information is not invented.
The full final prompt is [R3.txt](../prompt_templates/R3.txt). It distinguishes
source claims, direct observations, inferences and hypotheses; asks for source
attribution and uncertainty; prohibits memory/state allocation; and gives concise
per-type examples instead of embedding JSON Schema.

## Exact JSON contract

The top level has exactly one field, `results`, an array. Empty arrays are valid
and create no memory or IDs. All objects require `type`, nonempty `text`, a nonempty
unique `source_ids` list of supplied source identifiers, and `related_to`.

| Type | Additional required fields | Optional fields |
| --- | --- | --- |
| finding, observation, claim, inference, hypothesis | `qualification`: string; may be empty when none supplied | None |
| equation | `latex`: nonempty LaTeX string; `variables`: nonempty array of objects with exactly `symbol`, `description`, `units` | `origin`: `source` or `derived` |
| image | `url`: HTTP(S) URL or null; `reference`: nonempty string or null; at least one is required | None |

Every variable symbol and description must be nonempty; symbols must be unique.
Units are nonempty strings or null. JSON must escape LaTeX backslashes, e.g.
`"\\frac{a}{b}"`. Invalid controls and canonical markup delimiters are rejected.
The optional equation `origin` explicitly distinguishes model-derived expressions
from source-reported ones. If omitted, provenance records it as unspecified; Python
does not silently assert that it appeared in the source. All equations remain
unverified, regardless of the model's attribution.

An example sequence (structural illustration, not evidence):

```json
{
  "results": [
    {"type": "claim", "text": "A scoped source assertion.", "qualification": "Its limitations.", "source_ids": ["result-001"], "related_to": null},
    {"type": "equation", "text": "The associated expression.", "latex": "E = mc^2", "variables": [{"symbol": "E", "description": "Energy", "units": "joules"}, {"symbol": "m", "description": "Mass", "units": "kilograms"}, {"symbol": "c", "description": "Speed of light", "units": null}], "source_ids": ["result-001"], "related_to": 0, "origin": "source"},
    {"type": "image", "text": "The source figure description.", "url": null, "reference": "Figure 2", "source_ids": ["result-001"], "related_to": 0}
  ]
}
```

No unknown fields, memory drafts, filenames, Markdown documents, permanent IDs,
node assignments or dispositions are admitted. Image URLs must occur as complete
supplied URLs in the cited sources; fabricated suffixes/prefix matches fail.
Non-null figure references must occur in the cited research too (case/whitespace
normalization only). No images are downloaded or inspected by this code.

`related_to` is null or an actual integer (not a boolean) in array range. Forward
references are allowed; self-references and all cycles fail validation. These are
temporary references only. Python allocates every result's anchor before translating
relations to stable `RELATED_TO` references. This expresses association, not verified
support or entailment. Canonical citation edges use each result's supplied sources.

## Python-created memories and permanent representation

One nonempty R3 batch creates one research memory linked to the selected node.
Python derives its title from the question and summary from result text. It allocates
identity, renders prose safely, records the original source identifiers and batch
provenance, and writes the memory, equations and research-tree state in one existing
journaled commit. Empty results simply clear the pending batch without creating a
memory. Invalid results preserve pending evidence and the original state.

Array order is the canonical `Memory.units` order. Python uses `f...` anchors for
text, `e...` anchors for equations and new `i...` anchors for images. Result indices
are never permanent identities. A sequence can therefore render as
`r1#f1`, `r1#e1`, `r1#i1`, `r1#f2`, without moving media to an appendix.
Existing memories keep their original allocator fields; the image counter is
introduced lazily only when allocating an image. Existing IDs/history are not migrated.

- Text uses the standard proposition/explanation/provenance fields. `finding` is
  added to the finding-kind vocabulary; all extracted evidence statuses remain
  `unverified`. A model-selected result type is not a truth certificate.
- Equations retain external canonical JSON IDs such as `e_r1_1`. Their local unit
  contains a checked display projection: description, `$$` LaTeX block, symbol
  descriptions/units and origin/provenance. Validation compares the projection to
  the JSON definition, preventing silent display drift. Unknown units are not
  inferred. Variable display order is deterministic. Legacy compact equation
  references remain valid without changing old files.
- Images use a stable local `i...` unit with image Markdown, figure reference and
  provenance. A URL becomes `![description](<url>)`; absent URLs preserve the
  reference/description as text. The existing viewer displays canonical Markdown
  without fetching external image bytes.

Examples:

- [Mixed ordered memory](examples/ordered_r3_mixed.md): authored synthetic fixture
  with text, equation, image and hypothesis interleaved.
- [Its external equation JSON](examples/ordered_r3_mixed_equation.json).
- [Actual generated research memory](examples/ordered_r3_memory.md).

The mixed example is a storage/format demonstration, not a real scientific result.

## Minimal S2 compatibility

An equation/image-only memory is valid and must not require an invented textual
finding. S2's existing `source_findings` field can therefore reference the supplied
`e...`/`i...` anchors as well as `f...`. Its validator still requires all consumed
inputs to contribute actual supplied references. `SYNTHESIZES` keeps a synthesis
finding as its source, but may now target a finding, equation or image unit.
Other conceptual relationship restrictions are unchanged. The S2 prompt adds only
the sentence explaining those media-only references; its output structure is unchanged.
R4's prompt and code path remain unchanged.

The scripted demonstration was updated to the new R3 contract. It obtains two
separate batches per node to exercise synthesis with one memory per batch, rather
than asking a model to manufacture additional memories. Its explicit fixture budget
is 12000 bytes and the expected research count is 28, while runtime defaults and
scheduler/cadence code are unchanged. Old experiment/transcript files are not rewritten.

## Verification

The complete suite passes **133 tests**. New coverage exercises fixed R1 controls,
case/whole-word cleanup and downstream queries; exact three-variable R3 context;
source metadata/truncation; shared question deduplication; empty results; all text
types; mixed ordering; deterministic rendering; external equation JSON/LaTeX/units;
source-vs-derived attribution; figures with/without URLs; invented URLs/references;
invalid source IDs; range/type/self/cycle errors; stable references; media-only
synthesis; historical R3 transcripts; and exact viewer inputs/outputs.

A rejected equation batch is explicitly tested to roll back equations, memories,
IDs and research state together. Equation state was added to the controller's
rollback snapshot and prospective validation view because R3 now creates equations.
Existing journal/recovery, index, gardener, transport and viewer tests also pass.
Compilation, JavaScript syntax and whitespace checks pass. The restarted live
viewer API and headless Chromium show the final three variables, exact prompt,
real response, validation and generated memory. SHA-256 checks preserve
all **556 pre-existing research/transcript files**; R4 remains byte-identical.

## Real-model evaluation

Two bounded development calls used newly retrieved arXiv abstracts. The final
three-variable evaluation is **ordered-r3-arxiv-focused-20261025**. The preceding
prototype run remains separately recorded; no existing experiment was modified.

The final call retrieved the actual abstract of *A Theoretically Grounded Application
of Dropout in Recurrent Neural Networks* (arXiv `1512.05287v5`) through the arXiv API,
including authors, publication/update dates and source URLs. It was labelled
`content_kind: abstract`, not full text; the provider did not truncate it.
The local Qwen3.6-35B-A3B Q4_K_M endpoint received one user message, temperature 0,
and a 2000-token output ceiling. It reported **1366 input tokens / 437 output tokens**.

The model returned four ordered textual objects. They passed structural and source
validation, and Python committed exactly one memory with four findings/citation
edges. No equation or image was supplied by that abstract and none was invented.
The exact research, prompt snapshot, HTTP request/response, validation, committed
action and generated Markdown are in [ordered_r3_real.json](examples/ordered_r3_real.json).
The persistent experiment and exported full/concise transcripts remain under
`memory/research/ordered-r3-arxiv-focused-20261025/` and the matching transcripts path.

To repeat with a new experiment:

```bash
PYTHONPATH=src python3 examples/r3_research_check.py \
  --experiment another-ordered-r3-check --artifact /tmp/r3-check.json
```

The script supplies an operator query, performs actual arXiv retrieval, and invokes
R3 through the normal validation/storage path. It makes no R1, R4 or S2 calls.

## Limits

Structural validity does not establish entailment, mathematical correctness or
complete symbol coverage. Variables must be described, but no symbolic engine
checks whether the model omitted a symbol or derived the expression correctly.
Constants-only expressions without any described symbol are currently rejected.
Source/derived origin is a model attribution, retained as unverified; omitted origin
remains unspecified. Semantic and mathematical review are still required.

The real abstract-only test covers textual extraction, not real equation/figure
quality. Mixed-media storage is tested with authored fixtures. The model classified
some source-reported claims as findings/observations; Python preserves these types
but never promotes their evidence status. This is not independent verification of
the reported experiments or a benchmark of research judgment. No image downloads,
full-paper access, symbolic verification or automatic relationship discovery is claimed.

The source URL/reference checks are literal checks against supplied cited material,
not network accessibility/content verification. Relevant source metadata is preserved,
but mathematical-unit normalization and source equivalence are not inferred.

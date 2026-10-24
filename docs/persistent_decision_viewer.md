# Persistent research storage and local decision viewer

This increment was built directly on the merged `main` research implementation.
The initial increment changed storage defaults and added inspection/reviews.
The subsequent full state-prompt update is described below; research strategies
and synthesis scheduling remain unchanged.

## Launch and find the dropout R4 decision

From the Mira checkout on Fractal:

```bash
PYTHONPATH=src python3 -m mira viewer
```

When using an environment where Mira is installed, `python3 -m mira viewer` also
works. The system Python in this checkout needs `PYTHONPATH=src`. The default
address is **http://127.0.0.1:8767**. Use `viewer --port 8768` if that port is in use.
The server is local-only, uses Python's standard library, and loads all HTML,
JavaScript and CSS locally. It makes no model/search calls and has no external
assets, analytics, cloud service or automatic outgoing requests.

1. Select **monte-carlo-dropout** in the experiment list.
2. Choose **R4 · q1** in the action history, or filter to **R4 dispositions**.
3. Read the actual user/system prompts and expand the supplied-memory section.
   **Search evidence actually supplied** explicitly says it was not supplied.
4. Compare the **Previously retrieved external evidence** section with the input
   section. R2 retrieved two abstracts, but R4 received one generated memory.
5. Inspect the complete response, output contract and committed `kill` decision.
   The historical tree was `living` before R4 and `killed` afterward.
6. Optionally save a status/comments review at the bottom of the page.

The selected decision has a shareable local URL:

```text
http://127.0.0.1:8767/?experiment=monte-carlo-dropout&decision=00000003-0173b9b7698644fe97f6b5d097c29589
```

Previous/Next follow the filtered chronology. Click a tree node to jump to its
first recorded model decision. Refresh reloads the on-disk history. The tree is
labelled as historical before the selected decision or recorded after an action;
current corpus files are labelled separately.

## One live store per experiment

```text
memory/                              # ignored by Git; local data only
  research/<experiment>/
    memories/*.md                    # existing canonical Markdown
    equations/*.json                 # existing canonical equations
    research/state.json
    research/results/*.json
    interactions/<sequence>-<id>/*    # original request/response/validation/outcome
    journal/*                        # existing operation journal and after-images
    events/*.json
    identity.json
    index.sqlite3                    # rebuildable
  transcripts/<experiment>/
    full.md
    concise.md
    imported-original.md             # optional original export, byte-preserved
  reviews/<experiment>/<decision>.json
  imports/<experiment>.json           # source, timestamp and copied-file digests
```

Interactions stay **inside their experiment's existing live root**, rather than
being duplicated under a second shared `interactions/` store. Canonical formats,
IDs, filenames and the journal protocol are unchanged. All raw requests/responses
remain ordinary persistent files. `memory/` is in `.gitignore`, and research data
is never automatically committed or uploaded. Backups remain the owner's concern;
Git ignoring a directory is not a backup policy.

The default root is this Mira checkout's `memory/` directory, independent of the
shell's current directory. Override it explicitly with global `--memory-dir PATH`
or `MIRA_MEMORY_DIR`. For packaged installations outside a source checkout, set
that override to the intended persistent data location. Paths within each corpus
remain relative. Existing explicit `--root PATH` commands still work, and **Phase 1
continues to default to `knowledge/` with its original snapshot layout**.

New `research-init` and `research-demo` commands create persistent experiments:

```bash
PYTHONPATH=src python3 -m mira research-demo --experiment fixture-demo
PYTHONPATH=src python3 -m mira research-init 'A new research question?' \
  --database arxiv --experiment my-question
PYTHONPATH=src python3 -m mira research-state --experiment my-question
PYTHONPATH=src python3 -m mira transcript --experiment fixture-demo --full
PYTHONPATH=src python3 -m mira transcript --experiment fixture-demo --concise
```

Omit `--experiment` for a fresh automatically named experiment on initialization.
When more than one experiment exists, commands that read/resume require an explicit
selection. Existing names are never overwritten or merged. Transcript commands for
catalog experiments print the transcript and also persist it under
`memory/transcripts/<experiment>/full.md` or `concise.md`; `--output PATH` can write
an additional explicit export. These are derived exports; the recorded interaction
files are unchanged. See `research_execution.md` for bounded real-run options.

## Explicit import; no silent migration

The original `/tmp/mira-real-dropout.9TANbP` and its exported transcript were still
available and have been imported as **monte-carlo-dropout** with:

```bash
PYTHONPATH=src python3 -m mira research-import /tmp/mira-real-dropout.9TANbP \
  --experiment monte-carlo-dropout --transcript /tmp/mira-real-dropout-transcript.md
```

This command is already completed here; rerunning with the same name is rejected.
It obtains a shared source lock, validates the existing live corpus/journal without
initializing or mutating the source, stages a copy, compares every copied file's
SHA-256 digest, fsyncs the copy, and publishes a new directory. It copies the complete
journal, original interaction records and index as well as canonical research.
The original exported transcript is also preserved byte-for-byte. Symbolic links,
conflicting target names and incomplete/invalid canonical transactions are refused.
A failed staging copy remains hidden under `.import-*` for inspection; it is not
automatically adopted or deleted. Import metadata records copied-file digests.

The real experiment was **not reproduced or replaced with scripted output**. Every
copied experiment file matched its original, and the originals remain intact.
Persistent exports are now in `memory/transcripts/monte-carlo-dropout/`. No new
scientific claims or research-quality improvement is asserted by this increment.

## Prompt templates and filled prompts

Editable templates for R1, R3, R4 and S2 are in the repository's
[`prompt_templates/`](../prompt_templates/README.md), with shared system text and
per-action user/contract files. Click **Prompt templates** in the viewer header to
review current unfilled files. Each decision has a **Filled prompt templates
actually sent** panel, followed by the exact filled system/developer/user messages.
New calls save template source text, source hashes, inserted values, filled messages
and the request digest before dispatch. The viewer checks those messages/digest
against the saved HTTP body; it never fills today's template to represent an old call.
The original dropout run has actual saved messages but no template-version snapshot,
so its missing provenance is explicitly labelled. The local `prompt-template-check`
fixture experiment preserves the initial templates, which retained the old prompt
wording and R4 evidence omission. Those historical requests remain unchanged.

The current templates now contain complete state tasks, instructions, named context
slots and JSON Schema output contracts. New R4 calls receive this node's search
history and normalized evidence, alongside linked memories; R1/R3 also receive
search history and explicit provider/strategy slots. The viewer exposes **State
task and exact output instructions** and **Filled information slots**, extracted
only from the saved request. Null and empty values are distinct. The isolated
`state-prompt-check` fixture demonstrates the new prompts across all four states.
See the [template guide](../prompt_templates/README.md) for slot definitions,
output requirements, context budgets and reproduction commands.

## What is recorded versus what is shown

Actual model inputs are decoded only from the saved `serialized_request` body,
including exact role messages, structured context and contract. When that body is
missing, a separately recorded request object may be shown with that limitation
explicitly labelled. Missing messages/evidence/memories are never filled from the
current state, available corpus or current prompt templates. The exact original
serialized body has its own expandable panel; raw responses include complete
malformed/rejected output and transport errors when recorded.

The viewer separates:

- **Actually supplied:** only material inside the recorded request.
- **Available corpus at the decision:** retained journal after-images preceding
  the decision's operation, marked included/not included. This historical replay
  is for availability only; it never supplies missing prompts.
- **Externally retrieved:** earlier committed R2 evidence, including source
  metadata and raw feed, whether or not any of it was later sent to this model.
- **Generated:** the model's response and any new canonical memories actually
  committed by that decision.
- **Current corpus:** latest files, explicitly separate from historical inputs.

Only audit events with a committed journal marker and matching event-file hash are
shown as verified committed actions. The independent outcome record can describe a
past commit even when today's corpus is damaged; warnings report unverified events.
An unfinished call is labelled **interrupted** (it may still be in progress), rather
than assumed failed or repeated. The viewer never runs recovery or retries calls.
If historical after-images are unavailable, availability/tree information is marked
missing; the original request remains inspectable independently of it.

Token usage is server-reported when present. Context utilisation is the original
serialized request's UTF-8 byte estimate plus the output reserve, relative to the
recorded selection/historical configuration budget. It is labelled an estimate,
not a measured token percentage. For this R4, the saved request is 5703 bytes;
including its 2048 reserve gives a conservative estimated 48.4% of the 16000 budget.
That alone does not establish whether the *right* information was supplied.

## Local decision reviews

The review form supports Approved, Questionable, Incorrect and Needs investigation,
plus free-text comments. Nothing is saved until Save review is pressed. Reviews
are separate versioned JSON files under `memory/reviews/`, with timestamped history,
atomic replacement and stale-write rejection. Reviews are isolated by experiment
and interaction ID, including when two imports share the same original IDs.
The research controller never reads these annotations, so they do not affect
prompts, memory status, scheduling or future behaviour.

The HTTP server only writes review files. All canonical research, interaction and
journal files are opened read-only. Review writes require same-origin access and
a local per-server token; the server rejects foreign Host/Origin headers. Research
text is displayed as text, not executable HTML. No arbitrary file-serving or
canonical-write endpoint is exposed.

## Verification and limits

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --check src/mira/viewer_assets/app.js
```

**90 tests pass**: all 75 previous tests and 15 new persistence/viewer tests. New
coverage includes persistent CLI defaults, Phase 1 preservation, exact import
bytes, collision and symlink rejection, experiment isolation, exact requests and
responses, missing/torn interactions, no current-state reconstruction, missing
historical payloads, status distinctions, committed-event verification, review
persistence/history/conflicts, read-only canonical access, local HTTP boundaries,
persistent transcript exports and Git ignoring research data.

A real localhost HTTP smoke test and isolated headless Firefox check loaded the
imported R4 decision, its 23 inspection sections and explicit absence labels with
no UI errors. A local screenshot is stored at
`memory/reviews/monte-carlo-dropout/viewer-check.png`; it is ignored by Git.

This is a lightweight single-user viewer. It scans on refresh instead of building
a second database, and does not push live updates. Large histories can be slow.
Missing old after-images prevent complete historical availability reconstruction;
we do not guess. Current files may be mid-operation if research is running; only
verified commit events are labelled committed. Unfinished calls cannot always be
distinguished from a currently executing call. No graphical brain analysis, presentation generation, automatic self-correction
or cloud hosting is included.

### Prompt-template follow-up verification

All **98 tests pass**, adding eight tests for saved template provenance, exact
compatibility with every historical fixture request, safe one-pass substitution,
CRLF/source edits affecting only new calls, missing/invalid templates, honest legacy
records, mismatch detection and the read-only template catalog. A local Firefox
check verified both a filled R4 template and all four current template sources.

### Full state-prompt follow-up verification

All **102 tests pass** after the full state-prompt update. Coverage checks named
slot binding, literal source text, explicit absence, undeclared-context rejection,
state tasks/output schemas, R4 failed/successful search evidence, historical prompts
remaining unchanged, exact recorded instructions in the viewer and bounded
synthesis through three levels with the larger prompts. Phase 1 tests still pass.
The scripted fixture uses an explicit 11500-byte-estimated budget with a 2048
output reserve; runtime defaults remain configurable at 8192 / 2048. No new real
LLM experiment has been run to assess these prompts' research quality.

The fresh local `state-prompt-check` demonstration finished 16 research actions and
five synthesis actions across three tree levels. All 17 recorded model calls have
verified filled template snapshots. An isolated Firefox check confirmed the R4
task, exact output instructions, filled slots/evidence and current source catalog.
The imported dropout corpus still matches its original source byte-for-byte.

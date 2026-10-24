# Mira LLM prompt templates

These are the actual files used to prepare model requests, not documentation-only
examples. The initial templates preserve the previous system/user message text
byte-for-byte. They expose the current generic system instructions and structured
JSON payload; no new task-specific instructions, decision policy or context
selection have been added in this change.

| File | Purpose |
| --- | --- |
| `system.txt` | Exact shared system message for every model call. |
| `R1.user.json`, `R1.contract.json` | Search-keyword generation and its output contract. |
| `R3.user.json`, `R3.contract.json` | Evidence interpretation/research-memory proposals. |
| `R4.user.json`, `R4.contract.json` | Node disposition: kill, exhaust, retry, retry_split, exhaust_split. |
| `S2.user.json`, `S2.contract.json` | Synthesis of at least two complete unconsumed memories. |

R2 searches a provider without an LLM. S1 is deterministic and makes no model call,
so neither has an LLM prompt template. No developer message is currently supplied.

## Filling and editing

Each user template has two placeholders:

- `{{ context_json }}` receives the complete assembled context as indented JSON.
- `{{ output_contract_json }}` receives that action's contract JSON.

Values are substituted once. Braces or apparent placeholders inside retrieved
text, questions or memories are data, never evaluated recursively. Rendering must
retain the action, complete context and output contract. Unknown placeholders or
malformed user JSON fail before a model call. Whitespace is retained; even an
added newline in `system.txt` becomes part of subsequent requests.

You can review/edit the files directly in the IDE. New requests reload them from
disk; edits do not rewrite old records. Additional task instructions can be written
as a JSON `instructions` field in the user template, while preserving the required
fields/placeholders. Changing the allowed response schema/decisions also requires
reviewing deterministic validation code; editing the descriptive contract alone
does not change what the controller accepts. No web-based template editor is added.

The default directory is the repository's `prompt_templates/`. Installed packages
include it under `share/mira/prompt_templates`. `MIRA_PROMPT_TEMPLATES` can explicitly
select another directory. Missing files fail rather than silently falling back to
an embedded or older prompt.

## What information is currently included

The templates **do not decide what evidence is retrieved or included**. Current
context builders supply:

- R1: root question, selected-node state, ancestor questions, directly linked
  memories and child-node records (often empty initially).
- R3: the above plus bounded `search_evidence`, including result text/source IDs.
  The complete raw provider feed is retained in the corpus but is not inserted.
- R4: root question, selected-node state, ancestor questions, directly linked
  memories and children. **Raw search evidence is not currently inserted.**
- S2: root/ancestor questions, selected-node state, complete selected input memories
  and relevant equation definitions.

An available corpus memory is not necessarily included in a particular request.
The HTML viewer keeps these distinctions visible; this change does not silently
supply additional information or improve the R4 policy.

## Verify in the HTML viewer

Click **Prompt templates** in the header to review current unfilled sources and
contracts. Select a decision to review **Filled prompt templates actually sent**,
then the filled system/user messages and exact serialized HTTP body.

Every new request record stores the source text and SHA-256 digest of each file,
inserted bindings, filled messages and request-body digest **before dispatch**.
Template metadata is not added to the model request. The viewer verifies that the
saved filled messages and body digest match the original recorded request; the
original body remains the authority. Known credential redaction still applies.

Older calls, including the original Monte Carlo dropout run, predate template
provenance. Their actual saved prompts remain fully inspectable, with **template
version not recorded** explicitly shown. The viewer does not fill current templates
and claim they were used for a historical call.

# Plain-text task prompts

Edit `R0.txt`, `R1.txt`, `R3.txt`, `R4.txt`, `R5.txt` and `S2.txt` independently. Each call
reloads its file and sends one user message. No generic system/developer prompt,
JSON Schema or hidden model pass is added. R2 and S1 are deterministic.

| Action | Strict variables | Response |
| --- | --- | --- |
| R0 | question, strategies | strategy identifier and brief reason |
| R1 | question, question_context, previous_search_terms, control_terms, memory_context | keywords list |
| R3 | question, question_context, research | ordered results list |
| R4 | question, question_context, research_results, search_history | decision and reason |
| R5 | question, question_context, research_results, max_children | ordered questions list (possibly empty) |
| S2 | root_question, question, node, ancestor_questions, input_memories, equations | title, summary, findings with exact input references |

R0 runs once during initialization when neither a named strategy nor an explicit
compatibility database list is supplied. Its available strategies include identifiers,
names, descriptions and ordered database lists. Python rejects unknown IDs or extra
response fields; failed selection leaves no initialized research state. Explicit
strategy initialization calls no LLM. R0 does not consume a research cycle and
never repeats for children. Its request, response, validation and outcome use the
same immutable interaction records as the other calls.

R1 uses relevant bounded untrusted memory excerpts. Earlier terms are soft guidance;
Python prohibits control terms. It requests one or two literal topic phrases;
arXiv combines them with explicit AND/quoted-field syntax in Python.
R3 supports findings, observations, claims, inferences, hypotheses, questions,
equations and images. Questions require source/derived origin. Python assigns
all stable IDs and creates Markdown in result order.

R4 chooses exactly kill, answered or retry. It cannot supply keywords or children.
R5 alone develops children, only for exhausted nodes, and receives **every direct
research memory** plus equation definitions, including consumed research. It does
not receive descendant/synthesis memories. S2 uses complete selected unconsumed
inputs, including stable question/equation/image anchors for those input types.

Use `{{variable}}` substitution. Every declared variable must occur and be bound;
unknown/malformed slots and undeclared values fail before dispatch. Values are
serialized as sorted, indented JSON, including scalar strings. Missing is never
silently replaced with null. Explicit null, empty string, list and object remain
distinct. Substitution runs once: braces inside supplied values stay literal.
Surrounding source text and line endings are preserved exactly.

Each interaction retains source text/hash, bound context, filled messages and the
serialized request hash. The viewer verifies historical snapshots against actual
saved request bytes. Editing templates affects future calls only; historical JSON
and plain-text records remain readable. New runs discard raw API envelopes. Unique normalized retrievals are temporary,
hash-checked files under `retrieved/`; compact provenance and source-processing
records remain canonical. Pending inputs survive restarts and journal recovery.
Completed retrievals can be pruned with the CLI. Exact model request snapshots
remain essential audit records and therefore still include the supplied excerpts.
Older canonical evidence and historical requests remain readable unchanged.

Set `MIRA_PROMPT_TEMPLATES=/absolute/path` for a separate template directory.
Otherwise templates load from the checkout or installed
`share/mira/prompt_templates`. Missing files fail without an embedded fallback.
Capacity assessments include actual R5 prompt overhead; changes to templates are
reassessed before future actions. Complete-input budget checks remain mandatory.

See [architecture](../architecture.md) and [execution commands](../docs/research_execution.md).
Test with `PYTHONPATH=src python3 -m unittest discover -s tests -v`.

# Proposed architecture amendments for review

`architecture.md` and `futureWork.md` were left unchanged. These proposed documentation amendments describe the requested implementation; the final section contains additional behavior that was **not implemented**.

1. **R3 sequence:** document one model call, scientific/proposal validation, optional bounded terminology enrichment, then one journal publication of final research/glossary/state/event after-images. Vocabulary failure retains valid science. Enrichment is neither a new action nor a separate research state.
2. **Glossary format:** add optional append-only `terminology` outcome history and authority-backed descriptions with exact text, type, scope, qualification, concept/preferred-name/alias identity, URL and retrieval time. Preserve existing research evidence and extractive paper-definition rules. Describe MeSH M concepts separately from D descriptor groupings; neither related headings nor abbreviations establish synonymy.
3. **Lookup execution:** document medical/biomedical gating, configurable two-term default budget, six-request ceiling, three-second request/eight-second R3 limits, one-second MeSH pacing, outcome distinctions, negative/failure caching and cooldowns. The derived SQLite schema marker and lookup queue rebuild from canonical records; response caches remain disposable project logs. Journal recovery never reruns external lookup.
4. **R1 validation:** replace whole-response concept rejection with per-component validation while retaining strict structural JSON checks. Preserve model wording and order; record rejected components. Deliberately empty or entirely completed selections retain scientific search-blocking semantics. An entirely invalid selection instead produces a rejected action and durable validation-block receipt, retaining valid discoveries and permitting other eligible work. It does not establish exhaustion or authorize another model call.
5. **R1 context and exports:** document bounded, canonical, source-attributed terminology excerpts, explicit description types/truncation and terminology-only labeling. Glossary views expose authority citations and lookup status without adding definitions to term-name search or changing other LLM prompts.

## Further behavior proposed, not implemented

- Add an explicit, journaled operator command to release an R1 validation block after inspection. Define its authorization and provenance; do not silently retry or mark the question exhausted.
- Introduce MedGen only after approving an exact-identity mapping and source-specific attribution/reuse allowlist. Its aggregate API's availability alone is insufficient permission to copy every source definition.
- Evaluate MeSH latency against the conservative default lookup budget before increasing limits. Candidate retention is preferable to allowing optional network work to dominate R3.
- Consider authority-backed glossary relationship provenance separately. This implementation does not turn broader/related MeSH concepts into equivalent definitions or fabricate scientific relationships.
- Review semantic search planning and extraction quality independently. Passing a five-word format check and retrieving an authority scope note do not prove a concept is useful for the selected question or that a scientific conclusion is supported.

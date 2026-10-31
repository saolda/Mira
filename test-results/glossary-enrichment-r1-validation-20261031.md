# Integrated glossary enrichment and R1 validation — 31 October 2026

## Result

Implementation commit: **`6fae4f5`**, with malformed-Unicode hardening in **`10a98db`**; separate test commits: **`c5ec193`** and **`1f1f257`**. R3 now enriches source-grounded terminology through optional deterministic NLM MeSH lookup after its existing model call. The final research, glossary, state and event after-images share the existing journal transaction and one glossary revision/commitment update. R1 retains independently valid concepts and reports rejected components without rewriting them or making corrective model calls.

The existing medical experiment was **not continued, initialized or reset**. All **1,042 inventoried existing memory/log files and symlinks** remained unchanged. Its seven glossary candidates therefore retain their original records. Demonstrations below distinguish mocked R3 processing from a separate live vocabulary lookup; live lookup results were not admitted to the research corpus without R3 source grounding.

Architecture, futureWork and all prompts other than R1 are unchanged. Proposed documentation amendments and deferred behavior are in [the separate review note](glossary-enrichment-architecture-proposals-20261031.md).

## R3 sequence, matching and persistence

1. The existing R3 call returns scientific results and optional terminology proposals. Python validates the science and verifies each proposed term, passage and source reference against the supplied source.
2. Accepted new terms and touched undefined candidates are prioritized for enrichment. A bounded SQLite queue also supplies older undefined candidates. Already checked negative matches do not starve unattempted candidates.
3. MeSH's official exact entry-term lookup identifies term URIs. Its SPARQL API supplies explicit term-to-**concept** links, preferred names, documented synonymous names, descriptor identifiers and scope notes. The parser requires a unique active concept, validates names/identifiers and rejects lookalikes, ambiguous identities, truncated responses and unsupported abbreviation equivalence. A shared descriptor is not concept equivalence. The original glossary term and ID are preserved.
4. Exact authority descriptions retain their type, scope, qualification, preferred name, aliases, M concept identifier, D descriptor links, source URL and retrieval timestamp. A scope note need not repeat the research term. Research-paper definitions retain their existing extractive validation. Existing sourced definitions and evidence cannot be removed; authority definitions are deduplicated by provider, concept, description type and exact text.
5. Only the **final enriched records** generate glossary after-images and the hash commitment. Scientific memories, glossary changes, state and event publish atomically. SQLite remains disposable; its schema marker upgrades the derived lookup queue by rebuilding from committed canonical records. Recovery applies saved after-images without contacting MeSH or recalling the model.

Medical and biomedical strategies enable lookup; unrelated strategies do not. Defaults are **two distinct terms, six HTTP requests maximum, three seconds/request and eight seconds/R3**; MeSH uses one-second request spacing. Its current protocol normally takes two requests/matched term and one/absent term. CLI controls are `--terminology-limit`, `--terminology-request-timeout` and `--terminology-timeout`; a zero term limit disables network lookup.

Validated outcomes and concepts are cached under project `log/terminology-cache/`. Repeated terms avoid HTTP calls; unchanged concept descriptions retain their original retrieval attribution. Different names still require identity resolution. Successful/negative results expire after a day; failures use a short cooldown, and HTTP `Retry-After` is respected. Cross-process provider locking prevents duplicate concurrent submissions. Budget limits, timeouts, malformed responses and unavailable APIs retain scientific results and distinguish `not_attempted`, `unavailable` or `error` from a confirmed `not_found`.

The mocked R3 integration demonstration enriches **one glossary record**, creates **one research memory**, uses **two mocked vocabulary requests** and makes only its **one R3 model call**. Tests also cover a later R3 enriching an existing candidate, stable IDs, repeated cache use without duplicate definitions, and a paper definition coexisting with an authority scope note. Crash injection at `prepared` and `before_commit` preserves the final commitment, source memory and glossary record through explicit journal repair, without additional vocabulary or model calls. Failure tests retain the research memory and candidate.

## Live API smoke test

The final separate live test used three terms, a six-request ceiling, ten seconds/request and a 45-second total allowance so it could inspect all three examples. It made **five actual HTTP calls in 17.128 seconds**, with **two matches, one confirmed absence, no ambiguity and no API failure**. An earlier development smoke pass made five calls with the same outcomes: **ten enrichment smoke-test calls total**, separate from API/documentation inspection. These are smoke-test settings, not changed production defaults. Full final scope notes and identity metadata are saved locally in `log/terminology-enrichment-smoke-20261031/results-final.json`. No production R3 action or production vocabulary call was executed against the retained experiment.

| Requested term | Result and identity | Description / qualification |
| --- | --- | --- |
| Bronchiolitis obliterans organizing pneumonia | Explicit entry-term match to **Cryptogenic Organizing Pneumonia**, [M0027812](https://id.nlm.nih.gov/mesh/M0027812), descriptor **D018549**, matching term **T055218** | A **462-character `scope_note`** was obtained. Its first sentence is “An interstitial lung disease of unknown etiology, occurring between 21-80 years of age.” Retrieval: 06:28:57.110445 UTC. |
| Organizing pneumonia | Exact preferred-name match to **Organizing Pneumonia**, [M000751452](https://id.nlm.nih.gov/mesh/M000751452), descriptor **D000092124**, matching term **T001110612** | A **335-character `scope_note`** was obtained. It describes granulation-tissue formation in alveolar ducts and alveoli. Retrieval: 06:29:04.583769 UTC. |
| Volume doubling time | `not_found`; no concept or definition attached | Exact reason: **“No exact MeSH canonical or entry-term match.”** This is an exact-name lookup result, not proof that the scientific concept is absent from all terminology resources. |

The first two terms resolve to **different concept identities**. The implementation does not merge them. The authority's returned scope notes are terminology data, not independently verified scientific findings or an answer to the medical question. Courtesy of the U.S. National Library of Medicine. Retrieved terminology may not reflect the most current NLM data; NLM does not endorse Mira.

The implementation follows the [official MeSH concept model](https://hhs.github.io/meshrdf/concepts) and [lookup/API documentation](https://id.nlm.nih.gov/mesh/lookup). **MedGen is not enabled.** Its documented [E-utilities access](https://www.ncbi.nlm.nih.gov/medgen/docs/help/) does not make all returned descriptions freely reusable: [definition sources](https://www.ncbi.nlm.nih.gov/medgen/docs/definitionsources/) include separately attributed external vocabularies. No source-specific reuse allowlist or trustworthy fallback equivalence was established in this change. The small provider interface is extensible, but a secondary adapter must establish those conditions before admission. No MedGen definition was copied or represented as MeSH content.

## R1 validation and context

The prompt's single concept-format instruction was replaced with exactly the requested three paragraphs. All other R1 text is unchanged.

JSON field names, list/string types, list limits and required reason remain strict. Python validates each string separately for length, grammar, provider names, prohibited terms and duplicates, retaining accepted items in model order. Rejected entries retain their field, original index, original text and precise failure. Controls are rejected as whole components; Python no longer deletes words from a concept to manufacture an acceptable substitute.

If the selected list is deliberately empty, normal `search_blocked → R4` behavior remains. If every selected item is invalid, valid discoveries still persist, but a rejected R1 event and durable `r1_validation_blocked` receipt replace search-exhaustion semantics. The node remains living. Other eligible nodes and scheduled work can proceed; otherwise the controller reports `validation_blocked`. There is no corrective model call or automatic retry. Raw/proposed responses, normalized accepted lists, rejection details and decision references remain inspectable.

A **read-only replay** of the previous experiment's rejected response (`00000030-8e2b72802c024c41b78915cc2fe09300`) now retains all four valid proposed discoveries and these two selected items:

```text
necrotizing pneumonia spiculated nodule
solitary fibrous tumor lung spiculated
```

The two six-word selections retain individual five-word-limit rejections. The replay made **zero LLM calls**, submitted **zero searches** and changed **no research state**. Model-selected wording is retained; format acceptance does not establish scientific relevance.

The existing bounded R1 glossary retrieval now prefers relevant source-defined entries slightly, retains useful candidates, and reads definitions from hash-validated canonical records. Authority descriptions are prioritized within the two-definition excerpt and expose concise source/concept identifiers, preferred names, aliases, description types, explicit truncation information and `terminology_only=true`. The integration test confirms that a subsequent R1 receives the new scope note and concept ID. Both the glossary byte budget and full-request model context checks remain enforced.

Markdown and HTML exports display authority/type/citation, qualifications and lookup states. Legacy research-definition layout remains compatible. Names and aliases remain the only HTML search fields. External text is escaped; citations accept only validated MeSH concept URLs, and no automatic network calls were added to the standalone view.

## Validation and limitations

Command: `PYTHONPATH=src python3 -m unittest discover -s tests -q`.

**417 tests passed in 57.326 seconds**, including deterministic lookup/malformed/timeout/rate-limit cases, cache/budget/pacing checks, no science loss (including malformed Unicode in a cached description), stable IDs, journal recovery and commitments, SQLite rebuild/migration, legacy formats, R1 partial/all-invalid/empty behavior, other-node scheduling, bounded enriched context, and export escaping/search behavior. Live services are not dependencies of the automated suite. Existing SQLite connection `ResourceWarning` messages remain non-failing.

Limitations: strict matching intentionally misses lexical variants; budget expiry can leave candidates pending; real API latency may exceed the conservative production limits even when the longer smoke test succeeds. A vocabulary match does not validate a scientific claim. MedGen needs a source-specific admission policy. An all-invalid R1 block is durable and has no automatic retry or new operator-unblock command; an explicit operator recovery interface is proposed for review. R4, R3, S1 and S2 prompts were not changed.

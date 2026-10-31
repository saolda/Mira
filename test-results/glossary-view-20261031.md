# glossaryView — 31 October 2026

Both `glossary-view` and the retained `glossary-export` command call the same exporter. The existing Markdown layout, Unicode casefold ordering and result keys remain compatible; the result additionally includes `html_path`.

Generated current-corpus exports: **6 complete canonical entries**.

- `memory/research/glossary.md`
- `memory/research/glossary.html`

```bash
PYTHONPATH=src python3 -m mira glossary-view
xdg-open memory/research/glossary.html
```

`PYTHONPATH=src python3 -m mira glossary-export` regenerates the same two views. Place `--memory-dir PATH` or `--root PATH` before the command to select another corpus; the existing `--experiment NAME` compatibility option and `glossary-rebuild` remain available.

Enumeration and alphabetical ordering use SQLite, with the existing refresh/rebuild mechanism. A full integrity audit and journal-bound record hashes ensure that every displayed entry comes from the complete canonical JSON, including all definitions, aliases, qualifications, evidence passages, source/evidence/node references and relationships. Truncated SQLite definition/alias projections never supply exported scientific text. Corrupt, stale or incomplete caches are repaired; canonical damage and incomplete recovery block publication.

The self-contained HTML uses inline CSS and JavaScript, stable term-ID anchors, linked relationship/evidence references, responsive typography and a sticky search panel. Search indexes only canonical names and aliases. It normalizes Unicode and whitespace, prefers exact/prefix matches, lists selectable canonical terms, counts matches, supports arrow keys and Enter, scrolls and temporarily highlights selections, and displays “No matching terms” when appropriate. All scientific content remains visible for ordinary Ctrl+F.

Untrusted text is escaped in Markdown and HTML. Script data uses safe JSON raw-text escaping, and search results use DOM text APIs. A restrictive, content-hashed CSP and the absence of external assets permit local `file://` operation without network requests. Both outputs are rendered and staged before atomic per-file replacement, with restoration of the previous pair on publication errors. Export writes no canonical or journal records and changes no SQLite schema. HTML is registered as a derived view for canonical reads and explicit generated-corpus resets.

Validation: **392 automated tests passed**, zero failures/errors/skips. New regressions cover Markdown compatibility, complete canonical records/provenance, ordering, empty glossaries, CLI aliases, term/alias and partial matching, Unicode/case/whitespace, exact/prefix ranking, keyboard and click navigation, highlighting, relationship links, injection prevention, inline/offline assets, CSP hashes, missing/corrupt/tampered index repair, deterministic output, recovery gates, staging/publication errors, symlink safety and canonical-state preservation.

Real headless Chromium additionally exercised the exported fixture via `file://` with networking disabled: alias search, Enter selection, temporary highlight expiry, no-match state, and desktop/mobile layouts all passed. The mobile viewport had no horizontal overflow; the selected entry remained below the sticky search panel. The only page request was the local HTML document, and no script errors occurred.

Preservation: the current-corpus export changed only the two derived glossary files. Canonical glossary records, research state, memories, journals, existing user files and execution logs are unchanged. No new persistent research experiment was initialized and no memories were deleted. `architecture.md`, `futureWork.md` and every LLM prompt are unchanged.

No known defects remain from validation. Scientific text is reproduced from canonical records without generation or reinterpretation.

# Fixed language files

These are corrected copies of 3 files from `languages/` that had real
data-integrity bugs (see reports/v2/cross_language_findings.md, section 0):

- `russian,L-f_FIXED.json` — original had invalid JSON (a stray leading
  character before the opening `{`). Fixed by removing it.
- `portugese.W-f_FIXED.json` — original had all keys flattened at the top
  level instead of nested under `"translations"`. Fixed by re-wrapping.
- `vietnamese.W-f_FIXED.json` — same structural fix as Portuguese.

To use: review these, then replace the originals in `languages/` (rename
to drop the `_FIXED` suffix and match your existing naming) once you've
confirmed they look right.

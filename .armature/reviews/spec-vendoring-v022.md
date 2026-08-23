# Review Verdict: spec-vendoring-v022

## Scope Compliance
- Declared scope: Vendor upstream specification document. Exactly two authorized file operations: (1) new file `spec/Limnalis-v0.2.2.md`, a byte-for-byte copy of the upstream Limnalis v0.2.2 consolidated specification sourced from the scratchpad; (2) edit to `spec/README.md` indexing the new document, marking the v0.2.1 PDF and conformance matrix as the prior edition retained for history, and noting the Appendix A.8 expression-grammar caveat.
- Files modified:
  - `spec/README.md` (modified, +4/-3 lines)
  - `spec/Limnalis-v0.2.2.md` (new, untracked, 108,055 bytes / 2,048 lines)
- Out-of-scope modifications: none. `git status --porcelain=v1 --untracked-files=all` and `git diff --cached` show no other tracked, staged, or untracked changes anywhere in the repository.

## Byte-Identity Verification
Compared sha256 directly rather than trusting the implementer's report:
```
ae43c998823b23e30b45b30b79c01f48c987bfe64f4293ff0115f7dcad0f0dd8  spec/Limnalis-v0.2.2.md
ae43c998823b23e30b45b30b79c01f48c987bfe64f4293ff0115f7dcad0f0dd8  scratchpad/Limnalis-v0.2.2.md
```
Hashes match exactly. The vendored file is byte-identical to the human-provided source of truth. PASS.

## README Accuracy Verification
Diff reviewed in full (`git diff spec/README.md`). All new claims about `Limnalis-v0.2.2.md` were spot-checked against the actual document content:
- "canonical reference for Limnalis v0.2.2" — matches document line 4 self-description verbatim.
- "13 primitive operations" — matches line 156 ("The evaluator is defined in terms of thirteen primitive operations") and the 13-row numbered table at lines 157-171.
- "conformance corpus cases A1-A14 and B1-B2" — all 14 Track A cases (A1-A14, lines 1833-1974) and both Track B cases (B1-B2, lines 1976-1981) are individually enumerated; also cross-referenced in Section 19 ("A1–A14, B1–B2", line 2037).
- Appendix A.8 caveat — verified against lines 1297-1299: "### A.8 Expression Grammar / Unchanged from v0.2. See the v0.2 specification for the full expression grammar..." The README caveat line ("the full expression grammar (Appendix A.8) is still defined by reference to the v0.2 specification, which is not vendored in this repository") accurately reflects this.
- Caveat line is present in the "Version note" section as required.
- No prior README content was lost: the original file (12 lines, commit f231e60) consisted of a title, one intro sentence, a 2-row table, and a "Version note" section. The new version (14 lines) preserves all of this structure — title, intro, now-3-row table, "Version note" heading — with only the intended row/sentence edits (new row added, v0.2.1 rows annotated "prior spec edition, retained for history," version note rewritten to name v0.2.2 as current and add the A.8 caveat).

Result: PASS.

## Sanity Check on Vendored Content
- First ~40 lines: title, author/date line, self-description as canonical v0.2.2 reference, feature summary line, and a "Reader's Guide" section — normal specification front matter, no conversational or tool-call artifacts.
- Last ~73 lines (through EOF at line 2048): Track B cases, "Remaining Open Questions," JSON Schema Package section (18-18.3), and "Settled AST Decisions" (Section 19), ending cleanly with "Limnalis v0.2.2 — end of specification, grammar/AST appendix, reference evaluator, conformance corpus, and schema package." This is a deliberate closing line, not a truncation.
- Full heading structure (`grep '^#{1,3} '`) shows sequential, well-formed sections 0 through 19 plus Appendix A.1-A.11 subsections — consistent with a genuine consolidated specification document, no stray artifacts.

Result: PASS.

## Invariant Compliance
| Invariant | Status | Notes |
|---|---|---|
| SCHEMA-001 | N/A | No schema or normalized-AST files touched. Changed paths (`spec/README.md`, `spec/Limnalis-v0.2.2.md`) are disjoint from all `enforced-by` paths (`schemas/`, `src/limnalis/schema.py`, `tests/test_schema_validation.py`). |
| MODEL-001 | N/A | No AST model files touched (`src/limnalis/models/` untouched). |
| MODEL-002 | N/A | No AST model files touched. |
| NORM-001 | N/A | No normalizer files touched (`src/limnalis/normalizer.py` untouched). |
| FIXTURE-001 | N/A | No fixture corpus files touched (`tests/` untouched). |

No `agents.md` exists scoped specifically to `spec/`; only the top-level `agents.md` exists, which is unaffected by this changeset.

## Verdict: PASS

## Required Changes (if FAIL or CONDITIONAL):
None.

## Rollback Recommendation: NO
Changeset is fully within declared scope, byte-identity is cryptographically verified, README claims are factually accurate and spot-checked against source content, no governed invariant paths (SCHEMA/MODEL/NORM/FIXTURE) are touched, and the vendored document shows no sanity anomalies.

# Review Verdict: spec-recovery-vendoring

## Scope Compliance
- Declared scope: vendor recovered specification artifacts from human-provided recovery package (`/tmp/.../scratchpad/recovery_pkg/`) into `spec/`; exactly 5 authorized operations (4 new files + 1 README edit).
- Files modified (`git status --porcelain --untracked-files=all`):
  - `M  spec/README.md`
  - `?? spec/Limnalis-v0.2.2-reconstructed.md`
  - `?? spec/Limnalis-v0.2.2-reconstructed.pdf`
  - `?? spec/Limnalis-v0.2.2-recovery-notes.md`
  - `?? spec/limnalis_conformance_matrix_v0.2.2.md`
- Out-of-scope modifications: none. No source (`src/`), `schemas/`, `tests/`, fixtures, or governance (`.armature/`) files touched. The implementer also did not vendor the schema/fixture JSON/YAML files present alongside the recovery package's spec artifacts (`limnalis_ast_schema_v0.2.2.json`, `limnalis_fixture_corpus_v0.2.2.{json,yaml}`, etc.) — correctly out of declared scope.

## Byte-Identity Verification (computed independently, not from implementer report)

| File | recovery_pkg SHA-256 | spec/ SHA-256 | Match |
|---|---|---|---|
| Limnalis-v0.2.2-reconstructed.md | `a8fa48e6...b035169` | `a8fa48e6...b035169` | identical |
| Limnalis-v0.2.2-reconstructed.pdf | `00d6fbb9...fc06213a` | `00d6fbb9...fc06213a` | identical |
| RECOVERY_NOTES.md → Limnalis-v0.2.2-recovery-notes.md | `8b543439...9067d1cf7b3` | `8b543439...9067d1cf7b3` | identical |
| limnalis_conformance_matrix_v0.2.2.md | `a77e367c...28fd809a921` | `a77e367c...28fd809a921` | identical |

All four full 64-character hashes matched exactly (truncated above for table width; full hashes were compared byte-for-byte via `sha256sum`). PDF was additionally confirmed to be a well-formed PDF 1.5 document (valid `%PDF-1.5` header, valid `%%EOF` trailer) rather than a mislabeled or corrupted file.

## Content Accuracy Verification

| README claim | Verified against | Result |
|---|---|---|
| Reconstructed .md has "complete EBNF expression grammar" that consolidated v0.2.2's Appendix A.8 defers to | `Limnalis-v0.2.2.md` A.8: *"Unchanged from v0.2. See the v0.2 specification for the full expression grammar..."* vs. reconstructed A.9 "Expression Grammar": full EBNF for `Expr`, `JudgedExpr`, `CausalExpr`, `EmergenceExpr`, `DeclarationExpr`, etc. | confirmed |
| Reconstructed .md has "full v0.2 declaration grammar" that Appendix A.5 defers to | `Limnalis-v0.2.2.md` A.5: *"TimeDecl, BindingDecl, FacetPolicyDecl, AssumptionDecl, BaselineDecl, EvidenceDecl, and EvidenceRelationDecl remain as in v0.2"* vs. reconstructed A.5/A.6: full EBNF for all seven of these exact declarations | confirmed |
| Recovery notes state confidence levels (grammar/AST high, exact prose medium/low) and "diff, don't replace" guidance | `Limnalis-v0.2.2-recovery-notes.md` §Confidence: "Grammar and AST: high" ... "Exact original prose... medium/low"; §Recommended repository treatment: "diff it against the reconstruction rather than replacing it silently" | confirmed, near-verbatim |
| Matrix contains all 16 cases A1–A14 + B1–B2 with canonical `.lmn`-language sources | `grep` of `### A\d+/B\d+` headings: exactly A1–A14, B1, B2 (16 headings); 16 occurrences of ` ```limnalis ` fenced source blocks (one per case) | confirmed |
| Version note: grammar now available via reconstruction, reconstruction caveat present, canonical-precedence line present | New version-note text names the reconstruction as the grammar source, explicitly caveats it as "a reconstruction, not the lost original," states `Limnalis-v0.2.2.md` "remains the canonical prose reference," and states verbatim "Reader precedence: canonical consolidated spec > reconstruction > v0.2.1 edition." | confirmed |
| No prior README content lost | Diffed working tree against `HEAD:spec/README.md`: all 3 original table rows and the substance of the original version-note sentence (Appendix A.8, v0.2 spec, not vendored) are preserved; diff is purely additive (3 new rows + 1 expanded sentence in the version note) | confirmed |

## Provenance Labeling (VERIFY item 4)

The README does not present the reconstruction as canonical. The new table row opens with "Reconstructed recovery of the original v0.2.2 specification — not byte-identical to the lost original (see recovery notes)," and the version note states the consolidated `Limnalis-v0.2.2.md` "remains the canonical prose reference" plus the explicit precedence chain "canonical consolidated spec > reconstruction > v0.2.1 edition." Distinction is clear and unambiguous. **Pass.**

Advisory (non-blocking): the reconstructed document's own YAML-adjacent subtitle reads "Consolidated specification — reconstructed canonical draft." Taken in isolation this phrase could be misread as the document self-declaring canonical status, though it sits two lines below a "Recovery notice" blockquote that immediately disclaims byte-identity and binds it to reconstruction status, and the README (the actual provenance-labeling surface under review) correctly subordinates it. This is inherent to the byte-for-byte-copied source content, not something the implementer had discretion to alter under the declared scope (item 1 required byte-for-byte fidelity), so it is not a scope or accuracy violation — noting it only so a future reader/editor of the recovery package is aware.

## Invariant Compliance
| Invariant | Status | Notes |
|---|---|---|
| SCHEMA-001 | N/A | No paths under `enforced-by` (`src/limnalis/schema.py`, `tests/test_schema_validation.py`, etc.) touched; changeset is entirely under `spec/`. |
| MODEL-001 | N/A | No `src/limnalis/models/*` touched. |
| MODEL-002 | N/A | No `src/limnalis/models/*` touched. |
| NORM-001 | N/A | No `src/limnalis/normalizer.py` or `tests/test_normalizer.py` touched. |
| FIXTURE-001 | N/A | No fixture corpus files touched; the recovery package's fixture JSON/YAML were available but correctly left un-vendored (outside declared scope). |
| SPEC-001 / SPEC-002 | N/A | These govern `.armature/ARMATURE.md` section numbering/cross-references specifically, not `spec/`. Not implicated. |

## Sanity Check (structure / artifact scan)
- `Limnalis-v0.2.2-reconstructed.md` (1759 lines): pandoc-style YAML front matter, recovery-notice blockquote, then coherent heading sequence (`# Limnalis v0.2.2` → Reader's Guides → `# 0.`…`# 15.` → `# Appendix A` with A.1–A.12 → `# 16.`…`# 18.`), ending "**End of reconstructed Limnalis v0.2.2 specification.**" No conversational, chat-turn, or tool-call artifacts found.
- `Limnalis-v0.2.2-recovery-notes.md` (29 lines): clean `# / ## ` structure (Status, Sources used, Confidence, Recommended repository treatment). No artifacts.
- `limnalis_conformance_matrix_v0.2.2.md` (1264 lines): clean `# / ## / ###` structure (Overview, Cases, then 16 case sections each with Track/Focus/Canonical source/AST expectations/Evaluation expectations/Diagnostics). No artifacts.
- Targeted grep for conversational leakage patterns ("as an AI", "I cannot", "I apologize", "as a language model", "Sure, here") across all three new `.md` files returned no genuine matches.

## Verdict: PASS_WITH_ADVISORIES

All five declared file operations are present and correctly scoped; nothing else in the working tree changed. All four copied artifacts are byte-identical (SHA-256) to their `recovery_pkg` sources. Every README claim checked against the actual content of the new files is true. Provenance labeling correctly subordinates the reconstruction to the canonical consolidated spec, with the exact requested precedence statement present verbatim. No governed invariant (SCHEMA-001, MODEL-001/002, NORM-001, FIXTURE-001) is implicated by this changeset. One non-blocking advisory noted above regarding wording internal to the byte-for-byte-copied reconstruction (not the README, and not something the implementer had latitude to change).

## Required Changes: none

## Rollback Recommendation: NO
No violation found; the advisory does not warrant rollback or remediation of this changeset.

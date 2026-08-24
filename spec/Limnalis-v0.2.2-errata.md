# Limnalis v0.2.2 — Specification Errata

This file records known errors and internal tensions in the vendored specification set (`Limnalis-v0.2.2.md`, the consolidated edition; `Limnalis-v0.2.2-reconstructed.md`, the reconstruction; the vendored schemas and fixture corpus). The vendored documents are immutable upstream material and are never edited; corrections are recorded here instead. Reader precedence is described in [README.md](README.md) — in short: the consolidated edition remains the canonical prose reference, but **for AST shapes specifically, the vendored JSON Schemas and then the reconstruction are more faithful than the consolidated Appendix A.9**, as several entries below demonstrate. Line numbers refer to the vendored files as of 2026-08-24.

Each entry states the erroneous claim, the evidence, which artifact is correct, and its status.

---

## E1. `ClaimNode.eval?: EvalNode` (consolidated A.9) — field does not exist

- **Claim:** Consolidated A.9 gives `ClaimNode` an optional `eval?: EvalNode` field (`Limnalis-v0.2.2.md:1343`).
- **Evidence:** The AST schema's `ClaimNode` (`schemas/limnalis_ast_schema_v0.2.2.json`, `$defs.ClaimNode`) declares `additionalProperties: false` with properties `{annotations, expr, id, kind, node, refs, semanticRequirements, usesAnchors}` — an `eval` key is *forbidden*, and the schema has no `EvalNode` `$def` at all (eval results live in the conformance-result schema, not the AST). The reconstruction's `ClaimNode` (`Limnalis-v0.2.2-reconstructed.md:1346-1355`) also omits it.
- **Correct artifact:** Schema and reconstruction agree against the consolidated text: claims carry no `eval` field; evaluation results are runtime/conformance artifacts.
- **Status:** Confirmed error in consolidated A.9. Implementation follows the schema.

## E2. `AnchorNode.term: TermSpecNode` (consolidated A.9) — orphan type; real type is `AnchorTermNode`

- **Claim:** Consolidated A.9 types the anchor term as `TermSpecNode` (`Limnalis-v0.2.2.md:1347`).
- **Evidence:** `TermSpecNode` is defined nowhere — not elsewhere in the consolidated edition, not in the reconstruction, not in the schema. The schema's real type is `$defs.AnchorTermNode`: a `oneOf` over `{kind: "symbol", value}`, `{kind: "claim", value}`, and `{kind: "expr", expr}`. The prose warrant (§9.1, both editions: `term: Term | ClaimId`) covers the symbol and claim variants only; the `expr` variant has **no prose warrant in either edition**. The reconstruction never defines an `AnchorNode` AST block at all (only `anchors: [AnchorNode]` in `BundleNode`, `Limnalis-v0.2.2-reconstructed.md:1302`).
- **Correct artifact:** The schema (`AnchorTermNode`) is what normalized ASTs must satisfy and what the implementation produces. The `expr` variant stands schema-only, with no prose authority.
- **Status:** Confirmed orphan type name in consolidated A.9; `AnchorTermNode` (including its unwarranted `expr` variant) undocumented in both prose editions.

## E3. `BundleNode.frame?: FrameNode` (consolidated A.9) — actually required, and pattern-or-frame

- **Claim:** Consolidated A.9 marks the bundle frame optional and types it `FrameNode` only (`Limnalis-v0.2.2.md:1304`).
- **Evidence:** The schema requires `frame` on `BundleNode` (`required` includes `frame`) and types it `$ref: FrameOrPatternNode`. The reconstruction agrees: `frame: FrameNode | FramePatternNode` with no optionality marker (`Limnalis-v0.2.2-reconstructed.md:1292`).
- **Correct artifact:** Schema and reconstruction: `frame` is required and may be a full frame or a frame pattern.
- **Status:** Confirmed error in consolidated A.9. Implementation (`BundleNode.frame: FrameOrPatternNode`, required) follows the schema.

## E4. Operator-glyph conflicts between editions (EMRG / UNDEF / NULL)

- **Claim:** Consolidated §13.2 (`Limnalis-v0.2.2.md:1082+`) gives status glyphs `△(EMRG)`, `⊥(PARA)`, `∅(UNDEF)`, `◇(NULL)`.
- **Evidence:** The reconstruction's glyph table (`Limnalis-v0.2.2-reconstructed.md:794-797`) gives `⧊`(EMRG), `⊥`(PARA), `⌀`(UNDEF), `⦰`(NULL) — three of four Unicode glyphs differ (only PARA agrees). The reconstruction is at least self-consistent: its EBNF uses the same glyphs (`EmergenceOp ::= "⧊" | "EMRG"`, line 1256; `NullTerm ::= "⦰" | "NULL"`, line 1281). The consolidated edition offers no grammar productions for its glyph variants.
- **Correct artifact:** Unresolvable against the lost original for the Unicode column. The ASCII aliases (`EMRG`, `PARA`, `UNDEF`, `NULL`) agree between editions and are what the corpus and the implementation use; the implementation accepts only the ASCII forms.
- **Status:** Recorded conflict; ASCII forms are authoritative in practice, Unicode glyph question left open.

## E5. Lint rules 11 and 15 differ between editions

- **Claim/Evidence (rule 11):** Consolidated: "Bare `|∞|` is illegal **in machine-checkable claims** unless kind is declared" (`Limnalis-v0.2.2.md`, §14 rule 11). Reconstruction: "Bare `|∞|` is illegal unless kind is declared" (`Limnalis-v0.2.2-reconstructed.md:954`) — the consolidated scopes the rule to machine-checkable claims; the reconstruction states it unconditionally.
- **Claim/Evidence (rule 15):** Consolidated: "If `requires_joint_with` applies or a matching JointAdequacy exists, combined use must check joint adequacy." Reconstruction (`:958`): "Required joint adequacy is checked **by exact active-anchor set and task**" — the reconstruction states a matching criterion (exact set + task) the consolidated does not.
- **Correct artifact:** No third arbiter for rule 11's scope qualifier; both readings are recorded. For rule 15, the reconstruction's exact-set-and-task criterion matches the consolidated §9.4 licensing prose and the implementation's joint-adequacy matching, so the reconstruction's wording is the more precise statement.
- **Status:** Recorded divergence; unresolved for rule 11, reconstruction preferred for rule 15.

## E6. `TransportResult.sourceAggregate`: required in §10.3, optional in §18.2

- **Claim:** Consolidated §10.3 lists `sourceAggregate: EvalNode` with no optionality marker (`Limnalis-v0.2.2.md:1020`), making it required.
- **Evidence:** Consolidated §18.2 (`:2023`) describes `TransportExpectation` as "status (required) + optional sourceAggregate, dstAggregate, per_evaluator", and the vendored conformance-result schema requires only `["status"]` on `TransportExpectation`. A `metadata_only` result has no source aggregate to carry, so the §10.3 "required" reading is unimplementable for that mode.
- **Correct artifact:** §18.2 and the schema (optional).
- **Status:** Confirmed internal contradiction in the consolidated edition; schema follows §18.2, as does the implementation (`TransportResult.srcAggregate: EvalNode | None`).

## E7. Rule 21's `note(…)` notation contradicts the grammar

- **Claim:** Both editions' lint rule 21 render the free-prose form as a call: consolidated "Free prose in meta must use note(…)"; reconstruction "Free prose in `meta` uses `note(...)`" (`Limnalis-v0.2.2-reconstructed.md:964`).
- **Evidence:** The grammar has no parenthesized note form: `NoteExpr ::= "note" String ;` (`Limnalis-v0.2.2-reconstructed.md:1263`). The vendored corpus uses the bare form (B1: `note "N-1 is acceptable …"`), and the implementation parses `note "…"` (keyword + string), not `note(…)`.
- **Correct artifact:** The grammar, corpus, and implementation agree: `note "…"`. Both editions' rule 21 notation is wrong.
- **Status:** Confirmed notation error in both prose editions.

## E8. Dimensioned literal `0.02_pu_per_min` (corpus B1) underivable from either edition's grammar

- **Claim:** The corpus is derivable from the published lexical grammar.
- **Evidence:** Vendored corpus case B1 contains the term `0.02_pu_per_min`. Both editions' lexical profiles (consolidated A.2; reconstruction lines 1013-1014) define `Number ::= ["-"] Digit {Digit} ["." Digit {Digit}]` (no unit suffix) and `Ident ::= Letter {Letter|Digit|"_"|"-"}` (must start with a letter). A digit-led token with a `_unit` suffix matches neither production, so no Term derivation exists for it.
- **Correct artifact:** The corpus is the conformance authority (FIXTURE-001); the grammar has a gap. The implementation's permissive lexer accepts the token (normalized as a symbol term).
- **Status:** Confirmed grammar gap in both editions; corpus and implementation agree in practice.

## E9. Consolidated §17.2 A11 narrative diverges from the vendored corpus A11

- **Claim:** Consolidated §17.2's A11 (`Limnalis-v0.2.2.md:1900+`) describes a two-session bundle (`s_shared` with `shared_state=true`, `s_isolated` with `shared_state=false`) driven by a context-sensitive baseline fixture `test://baseline/by_context_v1` (10 under nominal/t1, 20 under stress/t2).
- **Evidence:** The vendored corpus's actual A11 has a **single** session `s1` and uses fixtures `test://eval/baseline_v1` + `test://baseline/const10`; `by_context_v1` appears nowhere in it. The narrative's fixture and two-session shape are absent from the vendored corpus.
- **Correct artifact:** For conformance, the vendored corpus (FIXTURE-001). The narrative is not wrong as a specification of intended semantics — and the project-authored extension corpus now realizes it: **extension case D5** ("Shared vs isolated session baseline state (spec A11 narrative)", `fixtures/limnalis_extension_corpus_v0.1.*`) implements the by-context fixture with sessions `s_shared`/`s_isolated`, so the narrative's semantics are covered project-side.
- **Status:** Recorded divergence; covered by extension case D5.

## E10. Reconstruction's degrade rule omits the precondition-failure branch

- **Claim:** Reconstruction §7.1 degrade (`Limnalis-v0.2.2-reconstructed.md:537-546`): "Attempt preservation. If relevant detail is lost, apply the default degradation [table]" — loss is the only stated failure branch.
- **Evidence:** The consolidated §10.2 degrade rule (`Limnalis-v0.2.2.md:1002-1004`) conditions on **both** gates: "if preconditions hold and semantic_requirements ∩ lose = ∅, preserve; otherwise …". The reconstruction states the precondition gate for `preserve` (its §7.1 preserve, conditions 1-3) but drops it from `degrade`.
- **Correct artifact:** The consolidated (degrade is precondition-gated like preserve). The implementation refines the failure vocabulary: precondition failure under degrade yields `N[transport_precondition]` with status `blocked` (no truth-table degradation), and only requirement loss triggers the degradation table.
- **Status:** Confirmed omission in the reconstruction; consolidated + implementation agree that preconditions gate degrade.

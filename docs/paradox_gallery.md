# Track C Paradox Gallery

## Purpose

Track C encodes four classic paradoxes — the liar sentence, the Schwarzschild
singularity, the decoherence (Schrödinger) cat, and the Banach–Tarski
duplication — as ordinary Limnalis claim bundles and runs them through the
unmodified evaluation pipeline. The point is the **disclosure thesis**: when a
paradox is forced through the seven-part separation (claim, frame, assumptions,
model-status, evaluator, evidence, evaluation), it does one of two things.
Either it *dissolves* — what looked paradoxical turns out to be a frame error,
a notation artifact, or an unlicensed use of an idealization — or it *survives*
as an honestly recorded B or N verdict with a reason code that says exactly
which concern could not be discharged. Nothing has to be smoothed over, and
nothing explodes: the bundles below produce no contradictions in the machinery,
only disclosed ones in the results.

Read through the four architectural layers, the gallery sorts as follows:

| Case | Paradox | Layer reading | Headline verdict |
|---|---|---|---|
| C1 | Liar sentence | Notation-layer artifact: a sentence about its own truth predicate | `block(meta) = F` via the live `N AND B = F` fold |
| C2 | Schwarzschild r=0 | Fiction-layer overreach: the smooth-manifold idealization pushed past its licensed task | license `N[missing_binding]`; transport `N[transport_loss]` |
| C3 | Decoherence cat | Knowledge-layer conflict: two evaluators, two verdicts, one claim | `B[evaluator_conflict]` at claim and block level |
| C4 | Banach–Tarski | Fiction-layer overreach: a choice assumption plus a volume proxy used outside its assessed task | aggregate `T` carrying a `missing_binding` disclosure; license `N` |

Notice what is *not* in the table: no case leaves a residue at the **world
layer**. Each paradox, once its frame, assumptions, licensing, and evaluator
panel are stated separately, is fully accounted for by the notation, fiction,
and knowledge layers. The world-layer claims themselves either evaluate
cleanly or are explicitly deferred with a reason.

The four cases live in the project-authored extension corpus
(`fixtures/limnalis_extension_corpus_v0.1.yaml`, case ids `C1`–`C4`) and are
mirrored as standalone bundles in `examples/paradox_*.lmn` (byte-identical to
the corpus `source` fields; test-enforced). All verdicts below are the pinned
corpus expectations, produced by live evaluation — atom-level evaluator
bindings, real §4 pair-algebra composition, real licensing, real transport —
never echoed from claim-keyed fixtures.

To run them:

```bash
# Normalize any gallery bundle
python -m limnalis normalize examples/paradox_liar.lmn

# Schema-validate the extension corpus
python -m limnalis validate-fixtures fixtures/limnalis_extension_corpus_v0.1.yaml

# Execute the four cases through the conformance machinery
python -m pytest tests/test_extension_corpus.py -k Paradox
```

## C1 — Liar Forensics

**Corpus case:** `C1` · **Bundle:** `examples/paradox_liar.lmn`

"This sentence is false." If it is true it is false; if false, true. The
classical trap depends on one symbol doing three jobs at once: being a
sentence, asserting its own truth value, and being evaluated by the same
apparatus it talks about.

The bundle splits those jobs. The sentence itself enters as a non-evaluable
`note` claim (`l0`) — recorded, never evaluated. The truth-assignment attempt
enters as `l1: false(liar_sentence)`, where `liar_sentence` is simply an
undefined term for the truth evaluator, backed by an *active placeholder
anchor* (`a_liar_truth`) that carries zero adequacy assessments — there is no
assessed model of the liar sentence's truth to license the claim. The
self-reference itself enters as `l3: refers_to_itself(l3) judged_by
test://paradox/criterion/tarski_gate_v1`, where the criterion detects that the
judged inner expression names its own enclosing claim id.

| Claim | Truth | Support | License |
|---|---|---|---|
| `l0` (note) | non-evaluable — excluded from folding | — | — |
| `l1: false(liar_sentence)` | `N[undefined_term]` | absent | `N[no_adequacy_result]` (placeholder anchor, no assessments) |
| `l3: refers_to_itself(l3) judged_by …` | `B[self_reference]` | absent | T (no anchors used) |

| Block | Per-evaluator | Aggregate |
|---|---|---|
| `meta` | `ev_meta: F` | **F** |

The block fold is the flagship result: the evaluable set `{l1 = N, l3 = B}`
folds to **F** by the live pair algebra (`N AND B = F` — falsity support
survives while truth support vanishes). Diagnostics: none.

**What dissolved, what remains.** The "paradox" dissolves into a notation-layer
artifact: one undefined term plus one detected self-reference, each with its
own reason code. What remains is honest bookkeeping — a deferred truth
assignment (`N`), a flagged self-reference (`B`), and a meta block that is
*false*: this collection of meta claims does not hold together, and the fold
says so without any special-case liar machinery.

## C2 — Schwarzschild Forensics

**Corpus case:** `C2` · **Bundle:** `examples/paradox_schwarzschild.lmn`

At r = 0 the Schwarzschild solution predicts infinite curvature and infinite
density. Is there "really" a singularity? The classical presentation lets one
idealization — spacetime as a smooth Lorentzian manifold — answer questions
in two very different registers: predicting gravitational-wave signals (where
it is superbly validated) and describing the core itself (where nothing
validates it).

The bundle gives the idealization one anchor (`a_smooth_manifold`) with two
task-scoped assessments: `aa_pred` (task `prediction`, attested score 0.99
against threshold 0.95, method registered and agreeing) and `aa_core` (task
`description`, score declared `N` — the quantum-gravity core description is
open — with a registered method that declares the score not yet computable).
Geodesic incompleteness (`c1`) is claimed under the frame task `prediction`;
infinite density (`c3`) is claimed with `license_task=description` and
`requires [semiclassical_validity]`. A degrade-mode bridge (`b_to_core`)
extrapolates toward the core and declares `lose [semiclassical_validity]`.

| Claim | Truth | Support | License |
|---|---|---|---|
| `c1: geodesically_incomplete(…)` | `T` | absent | **T** (`a_smooth_manifold:prediction` = T) |
| `c2: curvature --> divergence_within_finite_time` | `T` | absent | T (no anchors used) |
| `c3: infinite_density(r_zero)` | `T` | absent | **`N[missing_binding]`** (`a_smooth_manifold:description` = N) |

| Adequacy record | Result |
|---|---|
| `aa_pred` | `T` (0.99 ≥ 0.95, attested) |
| `aa_core` | `N[missing_binding]` + error diagnostic `adequacy_method_binding_missing` |

| Transport query | Status | Source → Destination |
|---|---|---|
| `q_core` (`c3` over `b_to_core`) | `degraded` | `T` → `N[transport_loss]`, support `partial` |

Block `local` folds to `T`. The one pinned diagnostic is the
`adequacy_method_binding_missing` error on `aa_core` — the machine-readable
statement that the core-description score cannot currently be computed.

**What dissolved, what remains.** The apparent world-layer catastrophe
("infinite density exists") dissolves into fiction-layer accounting: the
smooth-manifold idealization is licensed for prediction and *not* licensed for
core description, and transporting the density claim toward the core loses the
semantic requirement it rides on. What remains is `T` locally (the equations
really do say this, inside the model), an unlicensed `N` where the model has no
assessed adequacy, and `N[transport_loss]` at the destination — a precise
statement of "the theory predicts, but does not describe, r = 0."

## C3 — Decoherence Cat Forensics

**Corpus case:** `C3` · **Bundle:** `examples/paradox_decoherence_cat.lmn`

Is the cat in a superposition or not? The classical presentation forces one
answer from two incompatible evaluation procedures — unitary dynamics says the
joint state is superposed; the collapse postulate says measurement has already
selected an outcome.

The bundle declares both procedures as first-class evaluators
(`ev_unitary`, `ev_collapse`) over the same micro-frame claim
`c_super: superposed(cat)`, under a `paraconsistent_union` resolution policy.
A second claim, `c_coherent: interference_pattern(cat) requires
[phase_coherence]`, is agreed `T` by both evaluators; a micro→macro
amplification bridge (`b_amplify`, mode `degrade`) declares
`lose [phase_coherence]`.

| Claim | Per-evaluator | Aggregate |
|---|---|---|
| `c_super` | `ev_unitary: T`, `ev_collapse: F` | **`B[evaluator_conflict]`**, support `conflicted` |
| `c_coherent` | `ev_unitary: T`, `ev_collapse: T` | `T`, support absent |

| Block | Per-evaluator | Aggregate |
|---|---|---|
| `local` | `ev_unitary: T`, `ev_collapse: F` | **`B[evaluator_conflict]`** |

| Transport query | Status | Source → Destination |
|---|---|---|
| `q_amplify` (`c_coherent` over `b_amplify`) | `degraded` | `T` → `N[transport_loss]`, support `partial` |

The block result pins the evaluation order: blocks fold **per evaluator
first** (`ev_unitary` folds `T AND T = T`, `ev_collapse` folds `F AND T = F`)
and only then aggregate (`paraconsistent_union({T, F}) = B`) — never
aggregate-then-fold. Diagnostics: none.

**What dissolved, what remains.** Nothing about the cat dissolves — and that
is the finding. The paradox is a knowledge-layer conflict, and the machinery
records it as exactly that: `B[evaluator_conflict]` with the per-evaluator
split preserved, rather than one interpretation silently winning. What *does*
resolve cleanly is the macro question: coherence does not survive
amplification (`N[transport_loss]`), which is why no macroscopic observer
meets a superposed cat.

## C4 — Banach–Tarski Forensics

**Corpus case:** `C4` · **Bundle:** `examples/paradox_banach_tarski.lmn`

In ZFC, a solid sphere can be partitioned into finitely many pieces and
reassembled into two spheres identical to the original. The "paradox" trades
on two hidden dependencies: the Axiom of Choice (which builds the
non-measurable pieces) and the intuition that *volume* applies to every set of
points.

The bundle makes both explicit. Two evaluators sit on the panel: `ev_zfc`
(choice available) and `ev_zf` (choiceless — registered and deterministic, but
with no binding for choice-dependent predicates). The volume intuition enters
as a proxy anchor `a_volume` whose only adequacy assessment is for the task
`measure_theoretic_volume` — not the frame task `derivation`. The Axiom of
Choice itself is recorded as an **active placeholder anchor** (`a_choice`)
plus a meta note (`m1`) — see the encoding notes below for why.

| Claim | Per-evaluator | Aggregate | License |
|---|---|---|---|
| `c1: duplicable(sphere)` | `ev_zfc: T`, `ev_zf: N[missing_binding]` | **`T`**, reason `missing_binding`, support absent | T (no anchors used) |
| `c2: volume_preserved(sphere)` | `ev_zfc: F`, `ev_zf: N[missing_binding]` | `F`, reason `missing_binding` | **`N[no_adequacy_result]`** (`a_volume` not assessed for `derivation`) |
| `m1` (note) | non-evaluable | — | — |

| Block | Per-evaluator | Aggregate |
|---|---|---|
| `local` | `ev_zfc: F`, `ev_zf: N` | `F` |
| `meta` (note only) | `ev_zfc: N`, `ev_zf: N` | `N[empty_block]` |

The adequacy store pins `aa_vol = T` for `a_volume:measure_theoretic_volume` —
the proxy is perfectly adequate *for its own task*; the license failure on
`c2` is purely about using it elsewhere. Diagnostics: none.

The aggregate on `c1` deserves a precise reading: `paraconsistent_union`
joins `{T, N}` to `T`, and — because there is no T/F conflict and exactly one
evaluator supplied a reason — that unique reason (`missing_binding`, from the
choiceless evaluator) is inherited onto the aggregate. This is a general
resolution-policy mechanism, not Track-C-specific behavior: the aggregate
truth stands, with the dissent's ground attached as disclosure.

**What dissolved, what remains.** The scandal dissolves into fiction-layer
bookkeeping: duplication is `T` *in ZFC*, visibly choice-dependent
(`per_evaluator` split plus the inherited `missing_binding`), and the volume
intuition is simply unlicensed where the derivation lives
(`N[no_adequacy_result]`). What remains is a theorem, an assumption disclosure,
and a proxy used out of scope — no spheres were harmed at the world layer.

## Reading the Verdicts

One line per recurring code (all except `no_adequacy_result` are names from
the spec's §8.5 reason taxonomy — see the vocabulary notes below):

- **`B[self_reference]`** — a criterion detected that a judged claim names
  itself; the claim is both asserted and undermined by its own form.
- **`B[evaluator_conflict]`** — one evaluator says T, another says F, and the
  resolution policy records both rather than choosing.
- **`N[undefined_term]`** — the evaluator has no definition for a term in the
  claim; truth assignment is deferred, not denied.
- **`N[transport_loss]`** — a claim's semantic requirement is on the bridge's
  `lose` list; under `degrade`, a decisive source truth degrades to N at the
  destination (support `partial`).
- **`N[empty_block]`** — a block whose evaluable claim set is empty (e.g. it
  holds only notes) folds to N.
- **`N[missing_binding]`** — a referenced resolution target (criterion,
  method result, or per-evaluator predicate binding) is unavailable; in this
  gallery it marks both the unresolvable core-description score (C2) and the
  choiceless evaluator's non-verdict (C4).
- **`N[no_adequacy_result]`** — license-time code: an anchor used by the claim
  has no adequacy record for the resolved license task (implementation
  vocabulary; see below).

## Implementation Vocabulary and Encoding Notes

The gallery reports what the reference implementation actually emits. Four
points of precision, so none of the above is mistaken for native spec
behavior:

1. **License/adequacy reason vocabulary.** `no_adequacy_result` (anchor with
   no record for the resolved task — C1 `l1`, C4 `c2`) and `missing_binding`
   for a declared-`N`-score assessment (C2 `aa_core`) are the
   **implementation's** reason codes. The spec's reason taxonomy (§8.5)
   includes `not_yet_applicable`, and its assessment and licensing rules
   (§9.2, §16.6.4) assign exactly these situations — score declared `N`, or no
   adequacy record — to `N[not_yet_applicable]`. The implementation does not
   emit `not_yet_applicable` anywhere (`no_adequacy_result` is not a §8.5
   taxonomy name at all). This is a known, documented divergence — see the
   `ast_decisions` block of `fixtures/limnalis_extension_corpus_v0.1.yaml`.
2. **C4's Axiom of Choice record.** `AssumptionNode` exists in the AST model
   and schema, but the assumption declaration has no surface-grammar support
   yet — so the bundle records AC as an *active placeholder anchor* plus a
   meta note. It is a workaround, not native `assumption` syntax; do not read
   C4 as demonstrating a first-class assumption declaration.
3. **C2's declared unboundedness.** The spec grammar defines unbound
   references like `|inf:…|`, but the current normalizer rejects any baseline
   reference whose offset is not `0`. `c2` therefore writes the divergence
   claim as a DynamicExpr with a plain symbol target —
   `curvature --> divergence_within_finite_time` (normalized
   `op=approaches`) — not as a symbolic-infinity baseline reference.
4. **Bridge `via` URIs are declarative metadata.** The builtin
   `execute_transport` implements `metadata_only`/`preserve`/`degrade`
   entirely internally and never invokes a transport handler for those modes;
   `test://paradox/bridge/naive_extrapolation_v1` and
   `…/amplification_v1` appear in results only as provenance strings and are
   registered in the fixture pack as documentation markers, not executed
   code.

## Limits

The gallery does not answer the underlying questions. It does not say what is
at r = 0, does not decide between unitary and collapse dynamics, and does not
tell you whether to accept the Axiom of Choice. What it does is convert each
question into a well-posed verdict with a reason code — `N` where an answer is
genuinely not yet available, `B` where two committed procedures disagree, `F`
where a collection of commitments fails to cohere — each one addressable by a
later session step, a new binding, or an explicit policy decision. And part of
why the paradoxes stay contained is architectural: Limnalis has no entailment
closure. A `B` or an `N` is a recorded verdict about one claim under one
panel; it does not propagate as a premise into everything else, so a
contradiction disclosed is not a contradiction weaponized.

# Limnalis v0.2.2
**Consolidated specification with reader's guide**
Dave Medeiros | Panoptic Systems | March 2026
This document is the canonical reference for Limnalis v0.2.2. It incorporates all revisions from v0.2 through the unresolved-issues patch set and the schema freeze preparation: multi-evaluator semantics with resolution policies, first-class transport truth modes, session-based temporal evaluation, full JudgedExpr core semantics, assessment-based contestable adequacy with provenance, four-valued licensing results, settled AST pressure points, and a machine-checkable JSON Schema package.
Four-layer architecture · Seven-part separation · Belnap-Dunn semantics · Frame algebra · Fiction licensing · Multi-evaluator panels · Resolution policies · Transport truth modes · Session evaluation · Assessment-based adequacy · 25 lint rules · EBNF grammar · Canonical AST · JSON Schema package · Normalization rules · Reference evaluator · Conformance corpus (16 cases, 24 fixtures)
---
## Reader's Guide: Why Limnalis Exists
Limnalis was built to solve a specific class of failures that appear wherever claims, specifications, or decisions cross context boundaries without disclosing their assumptions. These failures are not implementation bugs. They are structural: the representational system being used cannot express the distinctions that would prevent the failure.
The following problems motivate the design. Each one is a case where existing specification languages, ontology frameworks, and formal methods fail silently because they collapse distinctions that must be kept separate.
| Problem | What Goes Wrong |
|---------|----------------|
| **Silent context collapse** | A claim holds in one frame (this population, this scale, this task) and gets applied in a different frame without anyone declaring what changed. The claim may still be true. It may not. Nobody tracked the crossing. |
| **Undisclosed idealizations** | Every engineering model and every architectural decision rests on assumptions the designer knows are not literally true but treats as adequate. No existing specification language can say "this is a fiction, it is adequate for prediction but not for explanation, and here is the evidence." |
| **Untraceable boundary crossings** | Information moves between teams, systems, agents, and abstraction levels. Some properties survive the crossing. Some are lost. Some new risks appear. Currently this is handled by tribal knowledge or hope. |
| **Evaluator conflation** | Different evaluators (human reviewers, static analysis, testing, runtime monitoring) assess the same claim and disagree. Current systems treat this as a bug. It is not a bug. It is a four-valued truth that should propagate with well-defined semantics. |
| **Evidence opacity** | Claims are asserted without declaring what evidence supports them, whether that evidence conflicts internally or with other evidence, or how confidence relates to truth. |
| **Notation-level paradoxes** | Formal systems produce apparent contradictions because they collapse proposition, frame, assumptions, evaluator, and evidence into a single undifferentiated statement. The "paradox" is a disclosure failure, not a world-level mystery. |
| **Fictions masquerading as facts** | Simplifying assumptions, proxy models, placeholder values, and aggregation shortcuts are treated as literal truth because no language exists to declare them as fictions with task-indexed, machine-checkable adequacy bounds. |
### The Common Root
Every problem in the table above has the same root cause: the language being used allows the author to leave critical context undeclared. A claim that holds in one frame gets asserted without naming the frame. An idealization gets treated as literal truth because no syntax exists to say otherwise. Evidence from conflicting sources gets merged without declaring the conflict. An evaluator's judgment gets presented as objective truth.
Limnalis prevents these failures not by restricting what can be asserted, but by requiring disclosure. You can assert a claim with no evidence, rely on an idealization you know is false, or transport a claim across a boundary where properties are lost. But you have to say so. The system forces the seven-part separation (proposition, frame, assumptions, model-status, evaluator, evidence, evaluation) that makes these failures visible and traceable instead of silent.
This is why Limnalis is best described as a disclosure language. It does not compute truth. It governs the conditions under which a claim is licensed to do work.
---
## Reader's Guide: Inside and Outside
One principle governs the architecture: never mix up the inside and the outside. The author declares structure. The evaluator computes results. The boundary between them is the canonical AST, which is produced by the parser/normalizer and validated against the JSON Schema package.
The author never writes evaluation logic. The evaluator never invents context. All outputs trace to declared inputs.
### What the Author Declares (Outside)
**Bundle declaration.** Frame (system, namespace, scale, task, regime), evaluator panel (who/what evaluates), resolution policy (how disagreements resolve), evidence and evidence relations, time context.
**Claims.** Local, systemic, and meta strata. Propositions with explicit refs, uses_anchors declarations, semantic_requirements for transport.
**Fictions.** Anchors (typed idealizations), adequacy assessments (task-indexed scores with producer, method, threshold), joint adequacy (composition licensing).
**Bridges.** From-frame and to-frame patterns, preserve/lose/gain/risk declarations, transport mode.
**Decision records.** Baselines, assumptions, bindings, normative judgments (judged_by).
**Tests.** Invariant and constraint declarations.
### What the Evaluator Computes (Inside)
**Phase 1: Resolve references.** Resolve all bindings, policies, evidence refs. Failures localize to N[missing_binding].
**Phase 2: Resolve evaluation context.** Construct active frame, evaluator panel, time.
**Phase 3: Initialize baselines.** Fixed / on_reference / tracked timing relative to session.
**Phase 4: Evaluate adequacy.** Resolve methods, compute/verify scores, compare to thresholds, check circularity, aggregate under adequacy policy.
**Phase 5: Materialize evidence.** Build per-claim evidence views, compute conflict and completeness scores.
**Phase 6: Evaluate claims (per evaluator).** Dispatch by expression type, four-valued logic for composition.
**Phase 7: Synthesize support.** Combine evidence view with truth result.
**Phase 8: Aggregate across evaluators.** Apply resolution policy to per-evaluator results.
**Phase 9: Fold blocks.** Per-evaluator first, then aggregate.
**Phase 10: Execute transport.** Evaluate bridge queries per step.
### The Boundary
The parser produces a normalized AST validated against the JSON Schema package. The evaluator consumes it. Neither side reaches across this boundary. The canonical AST is the contract between authoring and evaluation.
### Output
The evaluator produces: per-evaluator claim results, aggregate claim results, block results, license results, transport results, and diagnostics. Every output traces to declared inputs.
### Where External Systems Connect
Limnalis does not compute domain truth internally. Predicate evaluation, dynamic behavior, causal inference, and emergence detection are delegated to bound artifacts through the handler contracts (Section 16.4). External systems (models, simulators, policy engines, agent orchestrators) plug in at well-defined interfaces without modifying the evaluation pipeline.
---
## Reader's Guide: On "Don't Know" and the Case Against a Fifth Truth Value
A natural question arises: should Limnalis distinguish between "we looked and found nothing" and "we haven't looked yet"? If an evaluator has no evidence for a claim, is that the same as a claim that is deferred pending asynchronous evaluation?
The short answer: Limnalis already handles this distinction. The longer answer explains why it handles it through reason codes on N rather than through a fifth truth value, and why that design choice is load-bearing.
### N Is "Don't Know"
In the Belnap-Dunn four-valued logic, each truth value is a pair representing the presence or absence of truth-support and falsity-support:
- **T = (1,0)** -- truth-support present, falsity-support absent. The claim is supported as true.
- **F = (0,1)** -- falsity-support present, truth-support absent. The claim is supported as false.
- **B = (1,1)** -- both present. Conflicting evidence or evaluators. The claim is both supported and contradicted.
- **N = (0,0)** -- neither present. No information. The evaluator has nothing to say about this claim.
N is already the "don't know" value. It represents the complete absence of evaluative information. When an evaluator returns N, it means: I have no basis for asserting truth or falsity. This covers "haven't looked," "looked and found nothing," "can't evaluate in this frame," "missing a required input," and "deferred pending future evidence."
### Reason Codes Distinguish the Subcases
The spec requires that every N result carry a reason code (Section 8.5, Lint Rule 6). These reason codes are where the discrimination between different kinds of "don't know" actually lives:
| Reason Code | What It Means |
|------------|---------------|
| `N[missing_evidence]` | No evidence has been provided or located. The evaluator has nothing to work with. This is the "haven't looked" or "no data available" case. |
| `N[not_yet_applicable]` | Evidence or conditions may arrive later. The claim is deferred, not dismissed. This is the asynchronous evaluation case: re-evaluate when new evidence appears in a later session step. |
| `N[missing_binding]` | A required binding (policy, method, artifact) has not been resolved. The evaluation cannot proceed until the binding is available. |
| `N[out_of_scope]` | The claim is not evaluable in the current frame. A different frame or an explicit bridge is required. |
| `N[undefined_term]` | A term in the claim has no definition in the current context. |
| `N[missing_policy]` | A required policy (resolution, adequacy, evidence) is not declared. |
| `N[uninstantiated]` | The claim contains unresolved variables or parameters. |
| `N[transport_loss]` | Information was lost during a boundary crossing and the claim cannot be evaluated in the destination frame. |
| `N[circular_dependency]` | The evaluation depends on itself through an adequacy basis chain. |
The critical distinction between "haven't looked yet" and "looked and found nothing" maps to the difference between `N[not_yet_applicable]` (deferred, evidence may arrive) and `N[missing_evidence]` (no evidence is available to this evaluator). Both contribute zero truth-support and zero falsity-support. Both are N. But they carry different reason codes, which means downstream consumers (human reviewers, orchestrators, governance layers) can distinguish them and act accordingly.
### Asynchronous Evaluation Is Already Supported
The session and step model (Section 16.2) provides the machinery for deferred evaluation. A claim that returns `N[not_yet_applicable]` in step 1 can be re-evaluated in step 2 when new evidence, a new binding, or a new evaluator becomes available. The step model explicitly supports:
**Time progression:** each step can carry a different time context, allowing evidence to accumulate between steps.
**Frame overrides:** a later step can evaluate the same claim in a different frame where it becomes evaluable.
**Claim subsets:** a step can target specific claims for re-evaluation without reprocessing the entire bundle.
**Baseline re-resolution:** on_reference baselines re-resolve per step, capturing changes in the evaluation environment.
This means the transition from `N[not_yet_applicable]` to T, F, or B happens naturally as the session progresses. The evaluator does not need a fifth truth value to represent "pending." It needs a reason code that says "not yet" and a session model that supports re-evaluation. Both already exist.
### Why a Fifth Value Would Break the System
The four Belnap-Dunn values form a bilattice: a mathematical structure with two independent orderings (truth ordering and knowledge ordering) where conjunction, disjunction, and negation are well-defined and algebraically consistent. Every connective in Section 4, every block-folding rule, and every resolution policy aggregation depends on this structure.
Adding a fifth value (call it U for "unknown/unexamined") would require:
**Redefining all connectives.** What is T AND U? What is B AND U? What is NOT U? Each answer is a design choice that interacts with every other answer. The current system has 16 conjunction table entries. A five-valued system has 25. Each one must be justified and must preserve the algebraic properties (associativity, commutativity, absorption) that the evaluation pipeline depends on.
**Breaking the bilattice.** The clean two-dimensional structure (truth dimension and information dimension) does not naturally accommodate a fifth point. U would need to be placed somewhere in the lattice, and any placement either collapses it into an existing value (making it redundant) or creates asymmetries that break established identities.
**Complicating resolution policies.** Paraconsistent union is defined by componentwise OR on pairs. Priority order is defined by "first non-N." Both assume exactly four values. A fifth value would require revisiting every resolution policy definition and every conformance test that depends on them.
The reason-code approach preserves the bilattice, preserves all connective definitions, preserves all resolution policies, and provides strictly more discrimination than a fifth truth value would. `N[not_yet_applicable]` is not the same as `N[missing_evidence]` is not the same as `N[out_of_scope]`, and all three are operationally distinct in the evaluation pipeline. A fifth truth value would give you one additional distinction at the cost of rebuilding the entire algebraic foundation.
### The Design Principle
Limnalis separates truth-value from reason-for-truth-value. The four values govern algebraic composition (how claims combine through conjunction, disjunction, block folding, and resolution). The reason codes govern operational semantics (what to do about it, how to report it, when to re-evaluate). This separation is deliberate. Mixing operational distinctions into the truth lattice would compromise the algebraic properties that make the evaluation pipeline deterministic and composable.
The principle: use the minimum number of truth values needed for correct algebraic behavior, and handle all finer-grained distinctions through typed metadata on those values. Four values plus reason codes is strictly more expressive than five values without them.
---
## Reader's Guide: The Execution Model
The previous sections describe what Limnalis is for, how the authoring and evaluation sides are separated, and why four truth values plus reason codes are sufficient. This section states the abstract machine directly: its state, its primitive operations, and its evaluation loop.
The execution model is not classical three-address code. It is a typed evaluator micro-op machine. Each primitive runs against explicit step context, machine state, and services, and produces typed outputs plus diagnostics.
### Abstract Machine Signature
At the claim level, the evaluator is modeled as:
⟦claim⟧ : StepContext × MachineState × Services × History
        → ClaimResult × MachineState
At the expression level, delegated and internal expression evaluation still produces TruthCore values, but claim evaluation is no longer a simple function from Context and History to a single EvalNode.
This distinction matters because:
- sessions and steps affect baseline timing,
- baseline stores and adequacy results are stateful artifacts,
- diagnostics are observable outputs,
- claims may be non-evaluable (for example, NoteExpr),
- and every evaluable claim now yields per-evaluator results before aggregation.
### Step Context
The machine evaluates claims relative to an effective step context, not merely a bundle context.
```
StepContext:
  frame: FrameNode
  evaluators: [EvaluatorNode]
  resolutionPolicy: ResolutionPolicyNode
  time?: TimeCtxNode
  history: OpaqueHistory
  activeFacetPolicy?: FrameFacetPolicyNode
  sessionId: SessionId
  stepId: StepId
```
The effective step context is computed by merging:
- bundle.frame
- session.base_frame
- step.frame_override
and by choosing time/history from:
- step.time
- session.base_time
- bundle.time
- env.clock
- step.history_binding
- env.history
This is the context against which baseline resolution, claim truth, support, and transport run.
### Machine State
The evaluator maintains explicit machine state.
```
MachineState:
  resolutionStore: ResolutionStore
  baselineStore: Map<BaselineKey, BaselineState>
  adequacyStore: Map<AdequacyKey, AdequacyResult>
  evidenceViews: Map<ClaimId, ClaimEvidenceView>
  diagnostics: [Diagnostic]
```
Where:
- BaselineKey is session-scoped for fixed baselines when shared_state=true
- BaselineKey is step-scoped for fixed baselines when shared_state=false
- AdequacyKey is keyed by (anchor-or-joint-id, task, producer-set/policy context) as needed by the implementation
The machine state is not an optimization detail. It is part of the evaluator semantics.
### Uniform Primitive Signature
Each primitive is modeled uniformly as:
```
op(inputs, step_ctx, machine_state, services)
  -> (output, machine_state, diagnostics)
```
This is the normative execution envelope. Implementations may optimize internally, but the observable behavior must match this contract.
### Primitive Operations
The evaluator is defined in terms of thirteen primitive operations.
| # | Operation | Input | Output | Internal / Delegation Model |
|---|-----------|-------|--------|-----------------------------|
| 1 | **resolve_ref** | reference + machine state + resolver services | ResolvedArtifact or ResolutionFailure | Internal semantic op with pluggable resolver backend |
| 2 | **build_step_context** | bundle + session + step + env | StepContext or diagnostic | Internal |
| 3 | **resolve_baseline** | baseline id/spec + step context + baseline store | BaselineState | Hybrid: internal timing/cache semantics, delegated criterion resolution |
| 4 | **evaluate_adequacy_set** | anchor/joint-adequacy object + task + method/basis services | aggregated AdequacyResult | Hybrid: delegated method execution, internal aggregation/conflict logic |
| 5 | **compose_license** | claim + claim-local anchor set + task + adequacy results | LicenseResult | Internal |
| 6 | **build_evidence_view** | claim.refs + evidence store + evidence relations | ClaimEvidenceView | Internal |
| 7 | **classify_claim** | claim | evaluable / non-evaluable classification | Internal |
| 8 | **eval_expr** | ExprNode + claim + step context + evaluator + services | TruthCore | Hybrid dispatcher; logical composition internal, domain leaves delegated |
| 9 | **synthesize_support** | claim + evidence view + truth core + evaluator + services | SupportResult | Hybrid: default internal policy, optional delegated override |
| 10 | **assemble_eval** | TruthCore + SupportResult + evaluator id | EvalNode | Internal |
| 11 | **apply_resolution_policy** | per-evaluator EvalNode map + resolution policy + step context | aggregate EvalNode | Hybrid: built-ins internal, adjudicated delegated |
| 12 | **fold_block** | claim results for one block + resolution policy | BlockResult | Internal (uses apply_resolution_policy for block aggregation) |
| 13 | **execute_transport** | transport query + claim result + bridge + step context + services | TransportResult | Hybrid: mode semantics internal, remap/handler leaves delegated |
This is the normative instruction set.
### Why These Thirteen
This factoring is deliberate.
- `build_step_context` replaces a narrower `resolve_frame` primitive because the evaluator now computes effective frame, time, and history at step scope.
- `evaluate_adequacy_set` replaces the split between "evaluate adequacy" and "aggregate adequacy" because assessment execution and per-task aggregation are one semantic unit.
- `compose_license` replaces a narrower `check_license` name because the operation is not just a boolean check; it composes individual and joint adequacy results into a four-valued licensing result.
- `assemble_eval` is explicit because the transition from TruthCore + SupportResult to EvalNode is semantically load-bearing.
- `classify_claim` is explicit so NoteExpr and any future inert claim forms do not survive only as hidden branches.
### Operation Semantics
#### 1. resolve_ref
Resolves bundle-local ids, bindings, policies, evidence refs, anchor refs, baseline refs, bridge refs, and method/basis refs.
A failed required resolution does not by itself collapse the whole machine. It records a failure in the resolution store and localizes later evaluation to N[missing_binding] or N[missing_policy].
#### 2. build_step_context
Builds the effective step context from bundle, session, step, and environment inputs.
This operation subsumes:
- frame merge
- time selection
- history selection
- active evaluator panel selection
- active resolution policy selection
It is the machine entry point for session semantics.
#### 3. resolve_baseline
Resolves a baseline relative to the effective step context and the baseline store.
- fixed: one resolution per session if shared_state=true; one per step if shared_state=false
- on_reference: resolve at each reference under the current step context
- tracked: maintain a time-indexed object
This primitive owns timing and cache semantics. It may delegate criterion computation through resolveBaselineCriterion, but the timing model is internal.
#### 4. evaluate_adequacy_set
Evaluates all adequacy assessments relevant to one anchor or one joint adequacy object for one task.
This includes:
- method resolution
- basis resolution
- score computation or attestation
- threshold comparison
- method-conflict detection
- same-task aggregation under adequacy_policy
- missing-policy and circularity handling
The output is one aggregated AdequacyResult.
#### 5. compose_license
Computes the claim-local licensing result from:
- the claim's active anchor set
- task selection
- exact-set joint adequacy matching
- aggregated individual and joint adequacy results
It uses the operational severity rule:
- F if any required component is F
- else B if any required component is B
- else N if any required component is N
- else T
This is not propositional conjunction and remains distinct from world-claim truth.
#### 6. build_evidence_view
Constructs the declared evidence view for a claim:
- explicit evidence
- related evidence
- relevant declared evidence relations
- cross-conflict summary
- completeness summary
This is a per-claim artifact. It is not per-evaluator by default.
#### 7. classify_claim
Determines whether a claim is evaluable.
- NoteExpr is non-evaluable
- non-evaluable claims produce a ClaimResult with no per_evaluator map and no aggregate EvalNode
- non-evaluable claims are excluded from block folding
This makes NoteExpr a first-class machine action rather than a hidden branch.
#### 8. eval_expr
Evaluates an expression for one evaluator.
Internal:
- LogicalExpr recursion and four-valued connective semantics
Delegated or hybrid:
- PredicateExpr
- DynamicExpr
- CausalExpr
- EmergenceExpr
- DeclarationExpr (default internal fallback may apply)
- JudgedExpr (two-stage inner evaluation + criterion binding)
The output is TruthCore.
#### 9. synthesize_support
Computes support and confidence from:
- the declared evidence view
- truth-core provenance
- the evaluator's evidence policy, if any
Default support semantics remain internal. assessSupport and assessConfidence may override or refine them.
#### 10. assemble_eval
Combines:
- TruthCore
- SupportResult
- evaluator identity
into a final per-evaluator EvalNode.
This primitive is where:
- provenance is merged
- confidence is attached
- the per-evaluator result shape is finalized
#### 11. apply_resolution_policy
Aggregates per-evaluator EvalNodes into one aggregate EvalNode.
Built-in modes:
- single
- paraconsistent_union
- priority_order
Delegated mode:
- adjudicated
This primitive must aggregate the full EvalNode, not just truth.
For built-ins:
- truth aggregation follows Section 8.3
- support aggregation follows the policy's declared built-in rules
- provenance is the union of participating evaluators' provenance plus any policy provenance
- confidence is unset by default unless the policy defines a built-in rule or a delegated policy supplies one
#### 12. fold_block
Computes a block result in two stages:
1. fold evaluator-local claim evals using Limnalis conjunction
2. aggregate evaluator-local block results under the resolution policy
This operation owns the block-level result object. It excludes non-evaluable claims.
#### 13. execute_transport
Executes one transport query under the declared bridge transport mode.
Modes:
- metadata_only
- preserve
- degrade
- remap_recompute
This primitive is hybrid:
- mode semantics are internal
- remap/transport handler behavior may delegate through transportClaim
### Execution Loop
The evaluator executes in this order:
```
for session in request.sessions:
    machine_state = init_or_reuse_session_state(session)
    for step in session.steps:
        step_ctx, machine_state, diags = build_step_context(bundle, session, step, env)
        # Phase 1: reference and policy resolution
        machine_state = resolve_bundle_refs(bundle, machine_state, services)
        # Phase 2-3: step context and baseline service are now explicit
        # baselines resolve lazily or eagerly under resolve_baseline as needed
        # Phase 4: adequacy
        adequacy_results = {}
        for target in relevant_adequacy_targets(step, bundle):
            adequacy_results[target] = evaluate_adequacy_set(
                target, step_ctx, machine_state, services
            )
        # Phase 5-10: claim evaluation
        claim_results = []
        for claim in selected_claims(step, bundle):
            classification = classify_claim(claim, step_ctx, machine_state, services)
            if classification.evaluable is false:
                claim_results.append(
                    ClaimResult(
                        claimId=claim.id,
                        evaluable=false,
                        diagnostics=classification.diagnostics
                    )
                )
                continue
            evidence_view = build_evidence_view(claim, step_ctx, machine_state, services)
            license_result = compose_license(
                claim, adequacy_results, step_ctx, machine_state, services
            )
            per_eval = {}
            for evaluator in step_ctx.evaluators:
                truth_core = eval_expr(claim.expr, claim, step_ctx, evaluator, machine_state, services)
                support_result = synthesize_support(
                    claim, evidence_view, truth_core, evaluator, step_ctx, machine_state, services
                )
                per_eval[evaluator.id] = assemble_eval(
                    truth_core, support_result, evaluator.id, step_ctx, machine_state, services
                )
            aggregate = apply_resolution_policy(
                per_eval, step_ctx.resolutionPolicy, step_ctx, machine_state, services
            )
            claim_results.append(
                ClaimResult(
                    claimId=claim.id,
                    evaluable=true,
                    per_evaluator=per_eval,
                    aggregate=aggregate,
                    license=license_result
                )
            )
        block_results = []
        for block in bundle.claimBlocks:
            block_results.append(
                fold_block(block, claim_results, step_ctx.resolutionPolicy, step_ctx, machine_state, services)
            )
        transport_results = []
        for query in step.transport_queries:
            transport_results.append(
                execute_transport(query, claim_results, bundle.bridges, step_ctx, machine_state, services)
            )
```
This loop is normative up to observable outputs. Implementations may optimize internally, but they must preserve:
- per-evaluator-first claim evaluation
- per-evaluator-first block folding
- adequacy-before-dependent-claims
- session-relative baseline timing
- declared transport semantics
- localization of failure
### Key Invariants
**Locality of failure.**
A missing binding, unresolved reference, or failed adequacy check degrades the affected claim or adequacy result to N[...] with a reason code. It does not infect unrelated claims.
**Per-evaluator before cross-evaluator.**
Claims are evaluated independently for each evaluator before aggregation. Blocks are folded per evaluator before block-level aggregation.
**Adequacy before claims.**
Adequacy results are computed before any dependent claim in the same step is evaluated.
**Transport is step-scoped.**
Transport runs after claim and block results exist for the current step.
**Reason codes are mandatory for B and N.**
This is how Limnalis preserves a four-valued algebra while retaining operational discrimination.
### The Internal / Hybrid / Delegated Split
The primitive operations do not split cleanly into only "internal" and "delegated." There are three categories.
**Pure internal semantic ops**
- build_step_context
- compose_license
- build_evidence_view
- classify_claim
- assemble_eval
- fold_block
**Hybrid orchestrators with pluggable backends**
- resolve_ref
- resolve_baseline
- evaluate_adequacy_set
- synthesize_support
- apply_resolution_policy
- execute_transport
**Delegated leaf computations**
- evalPredicate
- evalDynamic
- evalCausal
- evalEmergence
- evalJudged
- resolveBaselineCriterion
- executable adequacy methods
- transportClaim for remap_recompute
- adjudicated resolution bindings
This is the execution model: a fixed internal algebra and orchestration pipeline with explicit, typed delegation points for domain truth computation.
---
---
## 0. Architectural Layers
Limnalis has four architectural layers.
World layer. Claims about systems, entities, mechanisms, trajectories, thresholds, and emergent behavior. Expressed mainly through local and systemic claims.
Knowledge layer.
The layer of evaluation: who or what is evaluating, from what evidence,
with what support status, confidence, and provenance. Expressed through Evaluator, Evidence,
EvidenceRelation, Eval, and the frame’s epistemic facets such as observer.
Fiction layer.
Assumptions, idealizations, placeholders, proxies, aggregates, and adequacy
judgments. Expressed through Assumption, Anchor, JointAdequacy, and related license checks.
Notation layer. Surface syntax, operator symbols, ASCII aliases, and bindings to external artifacts such as equations, datasets, code, and policies.
These four layers are not the same thing as the local/systemic/meta strata.
Strata organize
claims by descriptive level. Layers organize the architecture of the language. A meta claim can
belong to the knowledge, fiction, or notation layer depending on what it is talking about.
### 0.1 Notation Layer Responsibilities
The notation layer is representational rather than truth-bearing. It governs how Limnalis claims
are authored, canonicalized, serialized, and linked across tools.
It has three responsibilities:
Representation. The notation layer defines the authored surface forms of Limnalis: sectioned
source text, operator symbols, ASCII aliases, shorthand forms, and binding references to external artifacts.
Canonicalization.
The notation layer defines how authored forms normalize into canonical
abstract syntax. This includes alias normalization, shorthand expansion, block identification,
and conversion into the canonical AST.
Interchange. The notation layer defines stable machine-readable representations for tooling,
storage, transport, and cross-tool validation. This includes schema-level serialization and the
stable representation of bindings to external artifacts such as equations, datasets, code, and
policies.
The notation layer does not determine world truth, evidence support, or fiction licensing by itself.
Those are handled by the world, knowledge, and fiction layers. Its role is to make those layers
authorable, canonicalizable, and interoperable without changing their semantics.
---
---
## 1. How to Read Limnalis
Limnalis is best thought of as three things at once: a type system for framed claims, a contract
language for models, and a systems DSL for epistemic hygiene.
It does not replace math, code, probability, or simulation. It wraps them in an explicit account
of where a claim holds, what assumptions are active, what baselines and boundaries are in play,
what fictions are being used, who or what is evaluating, what evidence exists, and how failures
at the edge are represented instead of hidden.
The net effect: it becomes much harder to smuggle universality, idealization, or ambiguity into
a statement without declaring it.
Three capabilities distinguish Limnalis from existing specification languages, ontology frameworks, and formal methods:
The fiction layer. Every engineering model rests on idealizations — simplifications the modeler
knows are false but treats as adequate for a purpose. Limnalis makes these idealizations typed,
task-indexed, and machine-checkable.
An idealization can be adequate for prediction (score
0.98, threshold 0.95) but inadequate for explanation (score 0.63, threshold 0.75). The world
claim doesn’t change. The licensing of the fiction changes depending on what you’re using it for.
No existing specification language captures this distinction. See Section 9.
Truth transport across frames. Claims don’t live in a vacuum — they hold in a specific frame
(system, namespace, scale, task, regime). When a claim crosses a frame boundary, Limnalis
requires a declared bridge that says what properties survive, what’s lost, what new risks appear, and what transport mode applies. Truth can be preserved, degraded, remapped and reevaluated, or blocked. This makes boundary-crossing auditable instead of silent. See Section
Multi-evaluator resolution. When multiple evaluators assess the same claim and disagree, the
result is not an error — it’s a four-valued truth (B[evaluator_conflict]) that propagates through
conjunction, block folding, and transport with well-defined semantics. Resolution policies (paraconsistent union, priority order, adjudicated) determine how disagreement resolves. See Section
The remainder of this document proceeds from motivation (Section 2–3) through formal foundations (Sections 4–8), the three novel layers (Sections 9–10), supporting machinery (Sections
11–15), and implementation infrastructure (Sections 16–19 and Appendix A).
---
## 2. Core Design Rule
Every Limnalis statement must separate seven things that are otherwise prone to collapse into
one sentence:
- Proposition — what is being claimed.
- Frame — where the claim is supposed to hold.
- Assumptions — what is being taken as active.
- Model-status — which terms are literal, idealized, proxy-like, aggregate, or placeholder.
- Evaluator — what process, agent, or institution is assigning truth/support.
- Evidence — what the evaluator has to work with.
- Evaluation — the resulting T / F / B / N, plus why.
Limnalis remains a meta-language for context, but in v0.2.2 the context itself has typed parts.
---
---
## 3. Motivating Example
Before the formal definitions, here is a complete Limnalis bundle for a real engineering scenario.
This is a power grid contingency evaluation where:
- Two measurement sources (SCADA and PMU) conflict about bus 7.
- The N-1 contingency idealization is adequate for prediction and control, but not for postmortem explanation.
- A bridge exists to a regional planning frame, but it loses phase angle and switching order
— so truth transport is metadata-only.
Reading this example, notice the seven-part separation in action: the claims (what is being asserted), the frame (micro-scale AC load flow under contingency), the evaluator (the grid model),
the evidence (SCADA and PMU readings with declared conflict), the anchor (N-1 as a typed idealization with task-indexed adequacy scores), the bridge (declared transport with explicit preserve/lose), and the evaluation results (T, B[source_conflict], F[threshold_not_met] depending
on what’s being asked).
Bundle:
id: Grid_Contingency_01
frame:
system: PowerGrid
namespace: ACLoadFlow
scale: micro
task: operations
regime: contingency
version: v2
facet_policy: fp_grid_ops
evaluators:
- id: ev_grid_model
kind: model
role: primary
binding: model://grid/aclf/v2
evidence_policy: policy://grid/evidence/default
inference_policy: policy://grid/inference/default
provenance_policy: policy://grid/provenance/default
resolution_policy:
id: rp_grid
kind: single
members: [ev_grid_model]
time:
kind: interval
start: 2026-03-06T09:00:00
end: 2026-03-06T09:00:30
baselines:
- id: margin
kind: point
criterion: ref b_margin_ref
frame:
system: PowerGrid
namespace: ACLoadFlow
scale: micro
task: operations
regime: contingency
evaluation_mode: on_reference
evidence:
- id: scada_bus7
kind: measurement
binding: data://scada/bus7
observer: operator_A
completeness: 0.93
internal_conflict: 0.02
- id: pmu_bus7
kind: measurement
binding: data://pmu/bus7
observer: sensor_cluster_3
completeness: 0.96
internal_conflict: 0.01
evidence_relations:
- id: er_bus7_conflict
lhs: scada_bus7
rhs: pmu_bus7
kind: conflicts
score: 0.72
refs: [audit://grid/bus7_disagreement_report]
anchors:
- id: a_nminus1
term: Nminus1
subtype: idealization
status: active
adequacy:
- id: aa_n1_pred
task: prediction
producer: ev_grid_model
score: 0.98
threshold: 0.95
method: sim://checks/n1_pred
- id: aa_n1_ctrl
task: control
producer: ev_grid_model
score: 0.91
threshold: 0.90
method: sim://checks/n1_ctrl
- id: aa_n1_expl
task: explanation
producer: ev_grid_model
score: 0.63
threshold: 0.75
method: audit://postmortem/n1_expl
bridges:
- id: b_micro_to_regional
from:
system: PowerGrid
namespace: ACLoadFlow
scale: micro
task: operations
regime: contingency
to:
system: PowerGrid
namespace: PlanningModel
scale: regional
task: planning
regime: n-1
via: model://aggregate_flow_map
preserve: [power_balance]
lose: [phase_angle, switching_order]
risk: [aggregation_reversal]
transport:
mode: metadata_only
local:
c1: overload(line_B)
c2: overload(line_B) =>[obs] voltage_drop(bus_7)
refs [scada_bus7, pmu_bus7]
systemic:
c3: voltage_instability EMRG when reactive_margin --> |0:margin|
while demand_ramp_gt(0.02_pu_per_min)
until load_shed(zone_2) uses [a_nminus1]
meta:
c4: declare Nminus1 as idealization
note "N-1 acceptable for dispatch prediction;
weak as restoration explanation."
Expected results:
- eval(c1) = { truth=T, support=supported }
- eval(c2) = { truth=B, reason=source_conflict, support=conflicted }
- eval(c3) = { truth=T, support=partial }
- adequacy(a_nminus1, prediction)=T, control=T, explanation=F[threshold_not_met]
- block_status(local) = T ∧B = B
- block_status(systemic) = T
---
---
## 4. Four-Valued Logic
T=(1,0) F=(0,1) B=(1,1) N=(0,0)
¬X = (fX,tX); X∧Y = (tX∧tY, fX∨fY); X∨Y = (tX∨tY, fX∧fY); X→Y = ¬X∨Y; X↔Y = (X→Y)∧(Y→X)
Conjunction table:
∧
T
F
B
N
T
T
F
B
N
F
F
F
F
F
B
B
F
B
F
N
N
F
F
N
Why B∧N=F: B=(1,1) contributes falsity; N=(0,0) contributes nothing. Truth-support vanishes;
falsity-support remains. Result: (0,1)=F. This is the strict connective. Softer summary behavior
requires a declared policy.
---
## 5. Canonical Kernel
The kernel is a typed bundle, not just a line of notation.
Bundle:
id: BundleId
frame: Frame
evaluators: [Evaluator]
resolution_policy: ResolutionPolicy
time: TimeCtx?
claims: [Claim]
assumptions: [Assumption] = []
baselines: [Baseline] = []
anchors: [Anchor] = []
joint_adequacies: [JointAdequacy] = []
bridges: [Bridge] = []
bindings: [Binding] = []
evidence: [Evidence] = []
evidence_relations: [EvidenceRelation] = []
facet_policies: [FrameFacetPolicy] = []
Backward compatibility: old evaluator: Evaluator desugars to evaluators = [that evaluator]
plus resolution_policy = { kind: single, members: [that evaluator.id] }.
Frame:
system: Symbol
namespace: Symbol
scale: Symbol
task: Symbol
regime: Symbol
observer?: Symbol
version?: Symbol
facet_policy?: FrameFacetPolicyRef
Evaluator:
id: EvaluatorId
kind: model | human | agent | institution | ensemble | process
role: primary | adversarial | audit | auxiliary?
binding: BindingRef
evidence_policy?: BindingRef
inference_policy?: BindingRef
provenance_policy?: BindingRef
ResolutionPolicy:
id: ResolutionPolicyId
kind: single | paraconsistent_union | priority_order | adjudicated
members: [Symbol]?
order: [Symbol]?
binding: BindingRef?
TimeCtx:
kind: point | interval | window
t?: Timestamp
start?: Timestamp
end?: Timestamp
lag?: Duration
step?: Duration
Claim:
id: ClaimId
stratum: local | systemic | meta
kind: atomic | causal | dynamic | emergence | declaration
| judgment | note | logical
expr: Expr
uses_anchors: [AnchorId] = []
semantic_requirements: [Property] = []
annotations: Map<Symbol, Value> = {}
refs: [BindingRef | EvidenceRef] = []
eval: Eval?
semantic_requirements is used only by bridge truth modes. It does not change ordinary claim
evaluation. license_task is a reserved annotation key.
Evidence:
id: EvidenceId
kind: measurement | dataset | testimony | simulation | audit | derived
binding: BindingRef
observer?: Symbol
time?: TimeCtx
completeness: [0,1]?
internal_conflict: [0,1]?
EvidenceRelation:
id: EvidenceRelationId
lhs: EvidenceRef
rhs: EvidenceRef
kind: corroborates | conflicts | depends_on | duplicate_of
score: [0,1]?
refs: [BindingRef] = []
Binding:
id: BindingId
kind: equation | dataset | code | model | document | policy | ontology
target: URI
version?: Symbol
hash?: String
### 5.1 Expression Forms
Expr :=
Predicate(name, args...)
| Logical(op, args...)
    # op: not|and|or|implies|iff
| Causal(lhs, rhs, mode=obs|do, intervention?)
| Dynamic(subject, op, target, qualifiers?)
| Emergence(property, onset, persists_while?, dissolves_when?,
hysteresis?)
| Declaration(term, declared_as, within?)
| Judged(expr, criterion_ref)
    # any expr suffixed with judged_by
| Note(text)
### 5.2 Reference Resolution
All refs resolve against bundle-local collections or external URIs. Unresolved required refs are
lint errors; dependent evaluations yield N[missing_binding] or N[missing_policy].
---
---
## 6. Claims and Strata
local — entities, components, near-mechanistic relations. systemic — aggregates, distributions,
attractors, emergence. meta — claims about claims, frames, evaluators, anchors, bridges, baselines.
Rule 1: Only typed meta records are semantically active. note(“…”) is inert.
Rule 2: Claims inherit bundle frame and time unless they carry an explicit override.
### 6.1 Block Aggregation
Block truth is computed per evaluator first, then aggregated across evaluators under the bundle
resolution policy (see Section 8.6).
Within a single evaluator: block_status = fold(∧, evals_of_evaluable_claims_in_block).
- note(…) excluded from aggregation.
- Empty block →N[empty_block].
---
---
## 7. Frames, Patterns, and Facet Policies
A Frame is a resolved evaluation context.
A FramePattern is a partial facet assignment for
shorthand, projection, and bridge endpoints. Evaluation requires a resolved Frame.
Facet := system | namespace | scale | task | regime | observer | version
FramePattern:
facets: Map<Facet, Symbol>
facet_policy?: FrameFacetPolicyRef
FrameFacetPolicy:
id: FrameFacetPolicyId
order: { [Facet]: eq | PartialOrderRef }
independent: Set<(Facet, Facet)> = {}
depends_on: Set<(Facet, Facet)> = {}
DefaultFrameFacetPolicy: order[*]=eq, independent={}, depends_on={}.
### 7.1 Frame Operations
compatible(f1,f2); refines(f1,f2) [f1⊑f2]; join(f1,f2); project(f,S) →FramePattern; resolve(p,env)
→Frame.
Projection is a descriptive act. Truth reuse across a projection requires declared facet independence or an explicit Bridge. Otherwise: N[unsafe_projection]. Truth moves only by exact frame
match or explicit bridge.
---
---
## 8. Evaluation Semantics
At the claim level, the evaluator is modeled as:
⟦claim⟧ : StepContext × MachineState × Services × History
        → ClaimResult × MachineState
At the expression level, delegated and internal expression evaluation still produces TruthCore values, but claim evaluation is no longer a simple function from Context and History to a single EvalNode.
The full StepContext, MachineState, and primitive operation definitions are in the Reader's Guide: The Execution Model. The remainder of this section defines the semantic rules those primitives implement.
```
Eval:
  truth: T | F | B | N
  reason?: Reason
  support: supported | partial | conflicted | absent | inapplicable
  confidence: [0,1]?
  provenance: [BindingRef | EvidenceRef | EvaluatorId]
```
### 8.1 Field Semantics
truth — frame-relative, evaluator-relative. Not metaphysical.
support — evidence situation under active policy.
confidence — scalar from evaluator; not the same as truth.
provenance — enough traceability to identify evaluator, method, source.
### 8.2 Multi-Evaluator Model
Bundles may declare multiple evaluators with distinct roles. Every evaluable claim yields a perevaluator evaluation first, then an aggregate evaluation under the bundle’s resolution policy.
ClaimResult:
claimId: string
evaluable: true | false
per_evaluator?: { [EvaluatorId]: EvalNode }
aggregate?: EvalNode
license?: LicenseResult
diagnostics: [Diagnostic]
Frame.observer and evaluator are distinct.
May coincide but never by silent assumption.
A
claim’s per-evaluator results are computed independently before resolution.
### 8.3 Resolution Policies
Resolution policies aggregate per-evaluator results into a single aggregate eval.
single. Exactly one member. Aggregate eval is that evaluator’s eval.
paraconsistent_union. Take per-evaluator truth values as pairs: T=(1,0), F=(0,1), B=(1,1),
N=(0,0). Aggregate by componentwise OR across evaluators. One evaluator T, one evaluator F
→aggregate B[evaluator_conflict]. One evaluator T, one evaluator N →aggregate T. Two evaluators both N →aggregate N. Reason rule: if aggregate B arises because different evaluators
contributed truth and falsity, reason is evaluator_conflict; if a single evaluator already returned
B and no cross-evaluator disagreement is needed, its reason may be preserved; otherwise use
resolution_policy or the unique inherited reason. Support rule: conflicted if any evaluator returned conflicted or if truth aggregation yields B[evaluator_conflict]; else partial if any returned
partial; else supported if at least one returned supported; else inapplicable if all returned inapplicable; else absent.
priority_order. Use the first listed evaluator whose truth is not N. If all are N, aggregate is N.
This is the closest built-in approximation to layered verification.
adjudicated. The binding receives the per-evaluator eval map and returns the aggregate EvalNode. This is the escape hatch for governance stacks and orchestrators.
### 8.4 Evidence Conflict
Internal conflict: Evidence.internal_conflict. Cross-evidence conflict: EvidenceRelation(kind=conflicts).
Any evaluator-inferred conflict must appear in provenance.
### 8.5 Reason Taxonomy
B reasons: source_conflict, model_conflict, boundary_mix, aggregation_reversal, observer_split,
temporal_smear,
self_reference,
logical_composition,
evaluator_conflict,
adequacy_conflict,
method_conflict.
N reasons: out_of_scope, undefined_term, type_error, missing_binding, missing_policy, missing_evidence,
missing_joint_adequacy,
uninstantiated,
transport_missing,
transport_loss,
transport_precondition,
transport_mapping_missing,
not_yet_applicable,
unsafe_projection,
empty_block, logical_composition, circular_dependency.
F reasons (optional annotations): refuted, threshold_not_met, joint_inadequacy.
logical_composition is used when a B or N result is produced by applying the four-valued connectives to multiple sub-expressions and no single child reason uniquely determines the outcome.
Contributing child reasons are recorded in diagnostics.
B and N always require reason codes. F reason codes are optional annotations used when the
mode of falsity is operationally important.
### 8.6 Block Aggregation Under Multiple Evaluators
Blocks are folded per evaluator first, then aggregated across evaluators under the bundle’s
resolution policy.
The evaluator does not: aggregate claim truth across evaluators first, then fold the aggregate
claim truths into a block.
It does: (1) for each evaluator, fold the claims in the block using Limnalis conjunction; (2) then
aggregate those evaluator-local block truths under the resolution policy.
This avoids cross-evaluator conjunction artifacts that no evaluator actually endorsed.
BlockResult:
blockId: string
stratum: local | systemic | meta
per_evaluator: { [EvaluatorId]: T | F | B | N }
aggregate: T | F | B | N
claimIds: [string]
### 8.7 Symbol / Status Split
- ⊥is a surface token for paradox-marked expressions. ∅ is a surface token for undefinedness.
- B and N are evaluation outcomes, not the same objects as the surface tokens.
---
---
## 9. The Fiction Layer: Anchors, Adequacy, and Model-Status
This section describes the most novel component of Limnalis: the fiction layer.
Every engineering model, every simulation, every simplifying assumption is a fiction — a claim
the modeler knows is not literally true but treats as adequate for a specific purpose. Classical
specification languages have no way to represent this. A model is either in the spec or it isn’t.
Limnalis makes fictions first-class: typed, declared, task-indexed, and machine-checkable.
The key insight is that adequacy is not a property of a fiction in isolation — it’s a property of a
fiction for a task. The N-1 contingency idealization might be adequate for dispatch prediction
(score 0.98 vs threshold 0.95) but inadequate for restoration explanation (score 0.63 vs threshold
0.75). The fiction doesn’t change. Its licensing changes depending on what you’re asking it to
do. This is how real engineering works. Limnalis is the first specification language that captures
it.
### 9.1 Anchor Structure
Anchor:
id: AnchorId
term: Term | ClaimId
subtype: idealization | placeholder | proxy | aggregate
status: active | inactive | counterfactual
adequacy_policy: ResolutionPolicyRef?
adequacy: [AdequacyAssessment]
requires_joint_with: [AnchorId] = []
AdequacyAssessment:
id: AdequacyAssessmentId
task: Symbol
producer: Symbol
score: [0,1] | N?
threshold: [0,1]
method: BindingRef
basis: [BindingRef | EvidenceRef | ClaimRef] = []
confidence: [0,1]?
failure_modes: [Symbol] = []
Key changes from v0.2: producer is now explicit. method is still required. score may be present
as an attested output, or absent if the method computes it. Multiple assessments for the same
task are allowed and must be aggregated under adequacy_policy when relevant. This makes
adequacy a proper evaluated object instead of a bare numeric annotation.
JointAdequacy:
id: JointAdequacyId
anchors: [AnchorId]
adequacy_policy: ResolutionPolicyRef?
assessments: [AdequacyAssessment]
Backward compatibility: old adequacy record →single AdequacyAssessment under an implicit
single adequacy policy. Old joint adequacy record →single-assessment JointAdequacy.
### 9.2 Assessment-Level Semantics
Each AdequacyAssessment is evaluated independently.
1. Resolve method.
2. Resolve basis.
3. Determine or compute score.
4. Compare score to threshold.
Rules:
- If method is unresolved →N[missing_binding].
- If any required basis reference is unresolved →N[missing_binding].
- If score is present, treat it as an attested output of method.
- If score is absent, method must be executable and compute it.
- If score = N, result is N[not_yet_applicable].
- If an executable adequacy method is available, it may recompute or verify the assessment.
If computed and declared scores materially disagree under the active tolerance policy, the
assessment result is B[method_conflict].
### 9.3 Multiple Assessments Per Task
For a given anchor and task: collect all adequacy assessments for that task and aggregate them
under anchor.adequacy_policy. For a given joint-adequacy record and task: collect all joint assessments for that task and aggregate under joint_adequacy.adequacy_policy. If more than one
assessment applies and no policy is available: result is N[missing_policy].
### 9.4 Licensing Rules
Joint adequacy is required when any anchor names another via requires_joint_with or a matching
JointAdequacy exists for the task. Combined use is licensed iff all anchors are individually adequate and joint adequacy is met. Missing joint adequacy →N[missing_joint_adequacy]. Failed
joint adequacy →F[joint_inadequacy] for the composition judgment. A failed composition does
not automatically force the world claim false.
Exact-set matching rule: The relevant anchor set for joint adequacy lookup is the resolved,
deduplicated set of anchor ids named by Claim.uses_anchors for that claim. A JointAdequacy
record matches only if it names exactly that set and the same task. Supersets and subsets do
not satisfy the requirement. No composition inheritance across anchor sets is defined in v0.2.2.
### 9.5 Licensing Result (Four-Valued)
LicenseResult:
  claimId: string
  licenseTask: string
  anchors: [string]
  individual: { [AnchorId]: AdequacyResult }
  joint?: AdequacyResult
  overall: EvalNode
  reason?: string
License task resolution order: (1) claim.annotations[‘license_task’] if present; (2) evaluator-policy mapping from active bindings; (3) ctx.frame.task as final fallback.
Overall license aggregation uses a dedicated operational severity rule (not raw propositional
conjunction):
- F if any required individual or joint component is F.
- else B if any required component is B.
- else N if any required component is N.
- else T.
License results remain distinct from world-claim truth. A failed or conflicted license does not
automatically force the world claim false. It makes the modeling fiction unlicensed under the
active task and provenance conditions.
### 9.6 Circularity Rule
Adequacy assessments may cite ClaimRef in basis, but cycles are not allowed. If an adequacy
assessment depends on a same-bundle claim that directly or transitively depends on that adequacy result, the assessment resolves to N[circular_dependency]. This prevents the fiction layer
from silently self-justifying.
---
---
## 10. Bridges, Boundary Crossings, and Transport Semantics
Bridges formalize what happens when a claim crosses a frame boundary — a problem that every multi-scale, multi-team, or multi-system architecture faces but that existing specification
languages handle implicitly or not at all.
### 10.1 Bridge Structure
Bridge:
id: BridgeId
from: FramePattern
to: FramePattern
via: BindingRef
preserve: [Property]
lose: [Property]
gain: [Property] = []
risk: [aggregation_reversal | aliasing | temporal_smear
| observer_shift] = []
transport:
mode: metadata_only | preserve | degrade | remap_recompute
claim_map: BindingRef?
truth_policy: BindingRef?
preconditions: [BindingRef | Expr] = []
dst_evaluators: [EvaluatorId]?
dst_resolution_policy: ResolutionPolicyRef?
Backward compatibility: a bridge with no explicit transport block defaults to transport.mode =
metadata_only.
- ∅ is a crossing event. Bridge is a transport rule. Not the same thing.
- ∅ means the current frame no longer licenses evaluation. Crossing it yields N[out_of_scope]
unless a new frame or bridge is activated.
### 10.2 Transport Modes
metadata_only.
No truth transfer.
The bridge provides: destination pattern metadata, preserve/lose/gain/risk metadata, provenance only.
preserve.
Transport copies the source aggregate eval into the destination only if:
source
frame matches bridge.from; all transport preconditions hold; and claim.semantic_requirements
∩bridge.lose = ∅. If those conditions hold: destination aggregate eval = source aggregate eval;
support is copied; provenance is extended with bridge provenance. If not: destination aggregate
eval = N[transport_loss] or N[transport_precondition].
degrade. Transport attempts preservation, but weakens truth when lost detail matters. Default degradation rule: if preconditions hold and semantic_requirements ∩lose = ∅, preserve;
otherwise: T →N[transport_loss], F →N[transport_loss], B →B[boundary_mix], N →N. Default
support rule under degradation: if truth degrades due to loss, support becomes partial unless
truth_policy overrides it.
remap_recompute. Transport does not preserve source truth directly. Instead it: (1) maps
the source claim via claim_map; (2) completes the destination frame from bridge.to plus any
query-side completion; (3) evaluates the mapped claim in the destination frame; (4) under the
destination evaluator panel and destination resolution policy. This is the mode for nontrivial
frame-crossing, including cases where transported truth changes.
### 10.3 Transport Result
TransportResult:
claimId: string
bridgeId: string
status: metadata_only | preserved | degraded | transported
| blocked | unresolved | pattern_only
dstPattern: FramePatternNode
dstFrame?: FrameNode
mappedClaim?: ClaimNode | ExprNode
sourceAggregate: EvalNode
dstAggregate?: EvalNode
per_evaluator?: { [EvaluatorId]: EvalNode }
preserve: [string]
lose: [string]
gain: [string]
risk: [string]
provenance: [string]
### 10.4 Transport Lint
For any claim intended to use preserve or degrade, a linter should warn if semantic_requirements
is empty. Otherwise the transport claim is too underdeclared to justify truth carryover.
---
---
## 11. Baselines, Unbound Behavior, and Emergence
Baseline:
id: BaselineId
kind: point | set | manifold | moving
criterion: Expr | BindingRef
frame: FramePattern | Frame
evaluation_mode: fixed | on_reference | tracked
Defaults: point/set/manifold →on_reference; moving →tracked (required).
Baseline timing is defined relative to the evaluation session (see Sections 16.2 and 16.6.3):
- fixed — resolve once per session at first use or session initialization. Reuse the cached
value across later steps.
- on_reference — deferred resolver, evaluated lazily each time a referencing claim is evaluated, using the current step’s context.
- tracked — time-indexed resolver, required for kind=moving.
Important consequence: fixed and on_reference are observably different only when a session
has more than one step or a step-local context changes across evaluations.
Scalarization without declared reduction rule yields N[undefined_term].
Unbound kinds: |inf:asymptotic|, |inf:finite_time|, |inf:nonterminating|, |inf:externally_unbounded|.
### 11.1 Emergence
Emergence:
property: Expr
onset: Condition
persists_while?: Condition
dissolves_when?: Condition
hysteresis?: Condition
witness: [ClaimId] = []
---
---
## 12. Judgments and Normative Terms
Normative predicates are criterion-bound via judged_by.
Kernel form:
Judged(expr, criterion_ref). This prevents normative vocabulary from smuggling in as plain descriptive truth.
Example: safe(grid_state) judged_by policy://grid/safety_margin_v3
### 12.1 JudgedExpr Evaluation Semantics
JudgedExpr is a wrapper over any evaluable expression, not just a predicate.
Default judgment evaluation is two-stage: (1) evaluate the wrapped inner expression under the
active evaluator; (2) pass the inner truth result, the expression, the criterion reference, and the
current context to the criterion binding.
CriterionBindingContract:
evalJudged(innerTruth, expr, criterionRef, ctx, history, services)
-> TruthCore
Rules:
- If the criterion binding is missing or unresolved, result is N[missing_binding].
- Criterion bindings may use innerTruth directly or ignore it and re-evaluate against policy.
- Per-evaluator judged results are then aggregated under the normal resolution policy.
---
---
## 13. Surface Syntax and Operator Kernel
### 13.1 Surface Sugar
[behavior](subject), local{}, systemic{}, meta{}, declared_as, within, emerges_when, fictional_anchor.
### 13.2 Operator Kernel and ASCII Aliases
Logical: ¬(NOT), ∧(AND), ∨(OR), →(->), ↔(<=>).
Causal: ⇒obs, ⇒do.
Dynamic: ⟶(–>), ⇉k, ↭(OSC), ↺(CYC), ↦(|>), ><(><).
Boundary: ||(||).
Status: △(EMRG), ⊥(PARA), ∅(UNDEF), ◇(NULL).
Reference: |0:id|, |∞:kind|(|inf:kind|).
Approx: ≈(~=[metric,tol]). Refinement: ⊑(<=).
---
## 14. Lint Rules
1. Every bundle must declare at least one typed evaluator and a resolution policy.
2. Every evaluable claim must have an explicit or inherited frame.
3. Every frame pattern used for evaluation must resolve to a full frame.
4. Legacy @System:Namespace::Scope warns unless completed.
5. Every required external reference must resolve at evaluation time.
6. B and N must always carry a reason code.
7. Default block truth uses the conjunction in Section 4, folded per evaluator first, then aggregated under the resolution policy.
8. A block with no evaluable claims resolves to N[empty_block].
9. Bare |0| is illegal when more than one baseline is active.
10. kind=moving baselines must use evaluation_mode=tracked.
11. Bare |∞| is illegal in machine-checkable claims unless kind is declared.
12. =>[do] requires an intervention target or binding.
13. Every active anchor must declare at least one adequacy assessment for the current task.
14. Claims that materially depend on anchors should declare uses_anchors explicitly.
15. If requires_joint_with applies or a matching JointAdequacy exists, combined use must check
joint adequacy.
16. Missing required joint adequacy →N[missing_joint_adequacy].
17. Failed required joint adequacy →F[joint_inadequacy] for the composition judgment.
18. Every bridge must declare preserve and lose.
19. Truth transport across a projection without declared independence or bridge support is
illegal.
20. Normative predicates require judged_by.
21. Free prose in meta must use note(…).
22. Internal evidence conflict on Evidence; cross-evidence conflict in EvidenceRelation or
provenance.
23. For claims using preserve or degrade transport, warn if semantic_requirements is empty.
24. If more than one adequacy assessment applies for a task and no adequacy_policy is declared,
emit a warning.
25. Adequacy
assessments
with
ClaimRef
in
basis
must
not
form
cycles;
flag
circular_dependency.
Unless explicitly stated otherwise, lint warnings do not alter claim truth by themselves; lint
errors may still localize to N[…] outcomes where the underlying rule requires evaluation failure.
### 14.1 Diagnostic Code Registry for Normative Lint Rules
The following diagnostic codes are normative for rules 23–25.
Rule 23 — empty semantic_requirements under preserve/degrade transport.
- code: lint.transport.semantic_requirements_empty
- severity: warning
- phase: transport
- subject: ClaimId
- trigger: a claim is evaluated under preserve or degrade transport and Claim.semantic_requirements
is empty.
- effect: emit a warning diagnostic only; the transport result is otherwise computed normally
under the declared transport mode.
Rule 24 — multiple adequacy assessments with no adequacy_policy.
- code: lint.adequacy.missing_policy_multi_assessment
- severity: warning
- phase: license
- subject: AnchorId or JointAdequacyId
- trigger:
more than one adequacy assessment applies for the same task and no adequacy_policy is declared.
- effect:
emit a warning diagnostic and resolve the affected adequacy aggregation to
N[missing_policy].
Rule 25 — circular adequacy basis.
- code: lint.adequacy.circular_basis
- severity: error
- phase: license
- subject: AdequacyAssessmentId
- trigger: the basis dependency graph for an adequacy assessment contains a cycle through
ClaimRef or other adequacy-derived dependencies.
- effect:
emit an error diagnostic and resolve the affected adequacy assessment to
N[circular_dependency].
Message guidance: messages should name the affected claim, anchor, joint adequacy, or assessment id and should identify the relevant task when applicable.
---
---
## 15. Open Extensions
- Quantifiers and aggregation (forall, exists, proportions, cohorts).
- Probabilistic semantics beyond support and confidence.
- Full deontic logic for obligation / permission / prohibition.
- Richer domain-specific facet policies and dependency algebras.
- Bridge composition and proof obligations for chained transports.
- Explicit user-defined summary policies beyond the built-in block conjunction.
- Richer model-license propagation rules from anchor adequacy into downstream tooling.
---
## Appendix A: Grammar and AST
Canonical EBNF surface grammar, AST node definitions, normalization rules, and resolution
rules. All patches incorporated.
### A.1 Parsing Model
- Parse — raw AST preserving spelling, shorthand, block order, source spans.
- Normalize — desugar aliases and shorthand into canonical AST.
- Resolve / validate — resolve refs, complete frames, apply defaults, infer claim kinds, emit
lint/evaluation errors.
### A.2 Lexical Profile
Ident
::= Letter { Letter|Digit|"_"|"-" } ;
Number ::= ["-"] Digit{Digit} ["." Digit{Digit}] ;
String ::= '"' {Char|Escape} '"' ;
Uri
::= Scheme "://" UriChar{UriChar} ;
Symbol ::= Ident | String ;
Ref
::= Ident | Uri | String ;
Value
::= Number|Boolean|String|Uri|Symbol|ListLiteral
|MapLiteral|FramePattern ;
### A.3 Top-Level Structure
Document
::= BundleDecl EOF ;
BundleDecl ::= "bundle" Ident "{" BundleItem* "}" ;
BundleItem ::= FrameDecl | EvaluatorDecl | ResolutionPolicyDecl
| TimeDecl | BindingDecl | FacetPolicyDecl
| AssumptionDecl | BaselineDecl
| EvidenceDecl | EvidenceRelationDecl
| AnchorDecl | JointAdequacyDecl
| BridgeDecl | ClaimBlock ;
### A.4 Frames
FrameDecl
::= "frame" (FrameBlock | FramePattern) ";"? ;
FrameBlock
::= "{" FrameField* "}" ;
FrameField
::= ("system"|"namespace"|"scale"|"task"|"regime"
|"observer"|"version"|"facet_policy") Symbol ";" ;
FramePattern ::= "@{" [FacetAssign {"," FacetAssign}] "}"
| "@" Symbol ":" Symbol "::" Symbol ;
@System:Namespace::Scope normalizes to a FramePatternNode, not a full Frame.
### A.5 Supporting Declarations
EvaluatorDecl
::= "evaluator" Ident "{" EvaluatorField* "}" ;
EvaluatorField
::= "kind" EvaluatorKind ";"
| "role" EvaluatorRole ";"
| ("binding"|"evidence_policy"
|"inference_policy"
|"provenance_policy") Ref ";" ;
EvaluatorKind
::= "model"|"human"|"agent"|"institution"
|"ensemble"|"process" ;
EvaluatorRole
::= "primary"|"adversarial"|"audit"|"auxiliary" ;
ResolutionPolicyDecl ::= "resolution_policy" Ident "{"
"kind" ResolutionKind ";"
["members" RefList ";"]
["order" RefList ";"]
["binding" Ref ";"] "}" ;
ResolutionKind
::= "single"|"paraconsistent_union"
|"priority_order"|"adjudicated" ;
TimeDecl, BindingDecl, FacetPolicyDecl, AssumptionDecl, BaselineDecl, EvidenceDecl, and EvidenceRelationDecl remain as in v0.2.
### A.6 Anchors, Adequacy, and Bridges (patched)
AnchorDecl
::= ("anchor"|"fictional_anchor") Ident "{"
"term" TermSpec ";"
["subtype" AnchorSubtype ";"]
["status" AnchorStatus ";"]
["requires_joint_with" RefList ";"]
["adequacy_policy" Ref ";"]
AdequacyAssessmentDecl* "}" ;
AdequacyAssessmentDecl ::= "assessment" Ident "{"
"task" Symbol ";"
"producer" Symbol ";"
("score" (Number|"N") ";")?
"threshold" Number ";"
"method" Ref ";"
["basis" RefList ";"]
["confidence" Number ";"]
["failure_modes" RefList ";"] "}" ;
JointAdequacyDecl ::= "joint_adequacy" Ident "{"
"anchors" RefList ";"
["adequacy_policy" Ref ";"]
AdequacyAssessmentDecl* "}" ;
BridgeDecl ::= "bridge" Ident "{"
"from" FramePattern ";" "to" FramePattern ";"
"via" Ref ";"
"preserve" RefList ";" "lose" RefList ";"
["gain" RefList ";"] ["risk" RefList ";"]
[TransportDecl] "}" ;
TransportDecl ::= "transport" "{"
"mode" TransportMode ";"
["claim_map" Ref ";"]
["truth_policy" Ref ";"]
["preconditions" RefList ";"]
["dst_evaluators" RefList ";"]
["dst_resolution_policy" Ref ";"] "}" ;
TransportMode ::= "metadata_only"|"preserve"|"degrade"
|"remap_recompute" ;
### A.7 Claim Blocks and Claims
ClaimBlock ::= Stratum [Ident] "{" ClaimDecl* "}" ;
Stratum
::= "local" | "systemic" | "meta" ;
ClaimDecl
::= ClaimShort | ClaimLong ;
ClaimShort ::= Ident ":" Expr ClaimTail* ";" ;
ClaimTail
::= ("uses"|"refs") RefList
| "requires" RefList
| "annotations" MapLiteral ;
ClaimLong
::= "claim" Ident "{"
"expr" Expr ";"
["uses_anchors" RefList ";"]
["semantic_requirements" RefList ";"]
["refs" RefList ";"]
["annotations" MapLiteral ";"] "}" ;
### A.8 Expression Grammar
Unchanged from v0.2. See the v0.2 specification for the full expression grammar (JudgedExpr,
LogicalExpr, CausalExpr, DynamicExpr, EmergenceExpr, DeclarationExpr, NoteExpr, PredicateExpr, Term).
### A.9 Canonical AST Nodes (patched)
BundleNode:
node: "Bundle"
id: string
frame?: FrameNode
evaluators: [EvaluatorNode]
resolutionPolicy: ResolutionPolicyNode
time?: TimeCtxNode
bindings: [BindingNode]
facetPolicies: [FrameFacetPolicyNode]
assumptions: [AssumptionNode]
baselines: [BaselineNode]
evidence: [EvidenceNode]
evidenceRelations: [EvidenceRelationNode]
anchors: [AnchorNode]
jointAdequacies: [JointAdequacyNode]
bridges: [BridgeNode]
claimBlocks: [ClaimBlockNode]
EvaluatorNode:
node: "Evaluator"
id: string
kind: string
role?: string
binding: string
evidencePolicy?: string
inferencePolicy?: string
provenancePolicy?: string
ResolutionPolicyNode:
node: "ResolutionPolicy"
id: string
kind: "single"|"paraconsistent_union"|"priority_order"|"adjudicated"
members?: [string]
order?: [string]
binding?: string
ClaimNode:
node: "Claim"
id: string
kind: string
expr: ExprNode
usesAnchors: [string]
semanticRequirements: [string]
refs: [string]
annotations: { [key]: any }
eval?: EvalNode
AnchorNode:
node: "Anchor"
id: string
term: TermSpecNode
subtype: string
status: string
adequacyPolicy?: string
requiresJointWith: [string]
adequacy: [AdequacyAssessmentNode]
AdequacyAssessmentNode:
node: "AdequacyAssessment"
id: string
task: string
producer: string
score?: number | "N"
threshold: number
method: string
basis: [string]
confidence?: number
failureModes: [string]
JointAdequacyNode:
node: "JointAdequacy"
id: string
anchors: [string]
adequacyPolicy?: string
assessments: [AdequacyAssessmentNode]
BridgeNode:
node: "Bridge"
id: string
from: FramePatternNode
to: FramePatternNode
via: string
preserve: [string]
lose: [string]
gain: [string]
risk: [string]
transport: TransportNode
TransportNode:
node: "Transport"
mode: "metadata_only"|"preserve"|"degrade"|"remap_recompute"
claimMap?: string
truthPolicy?: string
preconditions: [string]
dstEvaluators?: [string]
dstResolutionPolicy?: string
Expression and term nodes remain unchanged from v0.2.
### A.10 Normalization Rules
All v0.2 normalization rules remain in force. Additional rules:
- Single evaluator →evaluators list + single resolution policy.
- Old adequacy record →single AdequacyAssessment with producer inferred from bundle
evaluator.
- Old joint_adequacy record →single-assessment JointAdequacy.
- Bridge without transport block →transport.mode = metadata_only.
- requires keyword in claim short form →semanticRequirements.
### A.11 Resolution Rules
All v0.2 resolution rules remain in force. Additional rules:
- Exactly one BundleNode, one bundle frame, at least one evaluator, exactly one resolution
policy.
- Resolution policy members must reference declared evaluator ids.
- Bridge transport.dst_evaluators, if present, must reference declared evaluator ids. ## 16.
## 16. Reference Evaluator
The reference evaluator is the normative orchestration layer for Limnalis v0.2.2.
### 16.1 Purpose
The reference evaluator is normative about: evaluation order, reference resolution, frame and
pattern handling, baseline timing, anchor-license checking, evidence-conflict materialization,
per-evaluator claim-level Eval, resolution policy aggregation, block folding, and optional bridge
transport.
It is not required to implement domain truth computation internally. Domain-specific predicate,
dynamic, causal, emergence, and criterion evaluation may be delegated to bound artifacts. A
conformant implementation may optimize caching and execution strategy, but must preserve
the same observable outputs for claim truth, B/N reason behavior, support classification, block
truth, resolution policy aggregation, and declared transport behavior given the same canonical
AST and environment.
### 16.2 Inputs and Outputs
EvaluationRequest:
bundle: BundleNode
env: EvaluationEnvironment
sessions: [EvaluationSession] = [implicit_default_session]
EvaluationEnvironment:
bindingResolver: Resolver
frameResolver?: Resolver
history: OpaqueHistory
clock?: TimeCtxNode
cache?: OpaqueCache
policyOverrides?: [string]
EvaluationSession:
id: SessionId
shared_state: true | false = true
base_frame?: FrameNode | FramePatternNode
base_time?: TimeCtxNode
steps: [EvaluationStep]
EvaluationStep:
id: StepId
time?: TimeCtxNode
history_binding?: BindingRef
frame_override?: FrameNode | FramePatternNode
claim_subset?: [ClaimId]?
transport_queries: [TransportQuery] = []
Backward compatibility: ordinary one-shot evaluation is sugar for one implicit session with one
implicit step.
#### 16.2.1 Effective Session and Step Context
For each EvaluationStep, the evaluator computes
an effective step context before baseline resolution or claim evaluation.
effective_frame
= merge(bundle.frame, session.base_frame, step.frame_override)
effective_time
= step.time ?? session.base_time ?? bundle.time ?? env.clock
effective_history = resolve(step.history_binding) if present, else env.history
Merge rule. Later facet assignments override earlier ones. A merge may combine full frames
or frame patterns. Any frame used for direct claim evaluation must resolve to a full FrameNode before evaluation. If the merged step frame cannot be resolved for direct evaluation, the
step emits a frame-phase diagnostic and dependent claims resolve locally to N[out_of_scope] or
N[missing_policy], as appropriate.
Baseline-local frame rule. A baseline’s own frame field overlays the effective step frame for
that baseline’s resolution only. This overlay does not mutate the effective step frame used by
other baselines or claims.
claim_subset rule. claim_subset limits which claims are evaluated in the step. It does not itself
force eager baseline materialization. A baseline is initialized eagerly only if an implementation
chooses session initialization for fixed baselines; otherwise it is resolved lazily at first relevant
use. Different implementations may choose eager or lazy initialization for fixed baselines, but
they must preserve the same observable outputs.
EvaluationResult:
bundleId: string
sessions: [SessionResult]
diagnostics: [Diagnostic]
SessionResult:
id: SessionId
context: ContextSnapshot
baselineStore: [BaselineState]
adequacyCache: [AdequacyResult]
steps: [StepResult]
diagnostics: [Diagnostic]
StepResult:
id: StepId
context: ContextSnapshot
claims: [ClaimResult]
blocks: [BlockResult]
transports: [TransportResult]
diagnostics: [Diagnostic]
Diagnostic:
id: string
severity: info | warning | error
phase: resolve | frame | baseline | license | evidence
| claim | block | transport
subject: string
code: string
message: string
### 16.3 Runtime Artifacts
ResolutionStore:
bindings: { [ref]: ResolvedArtifact | ResolutionFailure }
policies: { [id]: ResolvedPolicy }
evidence: { [id]: ResolvedEvidence }
anchors: { [id]: ResolvedAnchor }
baselines: { [id]: ResolvedBaseline }
bridges: { [id]: ResolvedBridge }
facetPolicies: { [id]: ResolvedFacetPolicy }
ContextSnapshot:
frame: FrameNode
evaluators: [EvaluatorNode]
resolutionPolicy: ResolutionPolicyNode
time?: TimeCtxNode
activeFacetPolicy: FrameFacetPolicyNode?
BaselineState:
baselineId: string
mode: string
status: ready | deferred | unresolved
value?: any
provenance: [string]
ClaimEvidenceView:
claimId: string
explicitEvidence: [EvidenceNode]
relatedEvidence: [EvidenceNode]
relations: [EvidenceRelationNode]
crossConflictScore?: number
completenessSummary?: number
LicenseResult:
claimId: string
licenseTask: string
anchors: [string]
individual: { [AnchorId]: AdequacyResult }
joint?: AdequacyResult
overall: EvalNode
reason?: string
AdequacyResult:
source: string
truth: T | F | B | N
reason?: string
provenance: [string]
ClaimResult:
claimId: string
evaluable: true | false
per_evaluator?: { [EvaluatorId]: EvalNode }
aggregate?: EvalNode
license?: LicenseResult
evidenceView?: string
diagnostics: [Diagnostic]
NoteExpr claims yield evaluable=false with no per_evaluator, no aggregate, and no license. Non-evaluable claims are excluded from block folding.
BlockResult:
blockId: string
stratum: local | systemic | meta
per_evaluator: { [EvaluatorId]: T | F | B | N }
aggregate: T | F | B | N
claimIds: [string]
TransportQuery:
claimId: string
bridgeId: string
dstCompletion?: FramePatternNode | FrameNode
TransportResult:
claimId: string
bridgeId: string
status: metadata_only | preserved | degraded | transported
| blocked | unresolved | pattern_only
dstPattern: FramePatternNode
dstFrame?: FrameNode
mappedClaim?: ClaimNode | ExprNode
sourceAggregate: EvalNode
dstAggregate?: EvalNode
per_evaluator?: { [EvaluatorId]: EvalNode }
preserve: [string]
lose: [string]
gain: [string]
risk: [string]
provenance: [string]
### 16.4 Bound Handler Contract
EvaluatorBindingContract:
evalPredicate(expr, ctx, history) -> TruthCore
evalDynamic(expr, ctx, history, services) -> TruthCore
evalCausal(expr, ctx, history, services) -> TruthCore
evalEmergence(expr, ctx, history, services) -> TruthCore
evalDeclaration(expr, ctx, history, services) -> TruthCore
resolveBaselineCriterion(spec, ctx, history, services)
-> BaselineResolution
assessSupport(claim, evidenceView, truthCore, ctx) -> SupportResult
assessConfidence(claim, evidenceView, truthCore, ctx) -> number?
CriterionBindingContract:
evalJudged(innerTruth, expr, criterionRef, ctx, history, services)
-> TruthCore
BridgeBindingContract:
transportClaim(claimResult, bridge, dstPattern, ctx, history,
services) -> TransportResult
AdjudicatedResolutionContract:
resolve(per_evaluator_evals, ctx) -> EvalNode
TruthCore:
truth: T | F | B | N
reason?: string
provenance: [string]
SupportResult:
support: string
confidence?: number
provenance: [string]
If a required handler is absent and no default fallback exists, the affected evaluation resolves to
N[missing_binding].
### 16.5 Normative Phase Order
For each session, and then for each step in that session:
1. Resolve references and policies.
2. Resolve the active step frame and evaluator panel.
3. Initialize or reuse the session baseline service.
4. Evaluate relevant adequacy assessments and joint adequacy groups.
5. Materialize declared evidence views per claim.
6. Evaluate each claim per evaluator.
7. Synthesize support per evaluator.
8. Aggregate claim results under the bundle resolution policy.
9. Fold blocks per evaluator, then aggregate block results.
10. Execute transport queries.
Two important clarifications: adequacy evaluation happens before dependent claims within the
step; transport is step-scoped, not bundle-global.
### 16.6 Phase Details
#### 16.6.1 Phase 1 — Resolve References
Resolve bundle-local ids, BindingRefs, FrameFacetPolicyRefs, evidence refs, anchor refs, baseline refs, bridge refs, resolution policy refs, and adequacy method/basis refs. If a required ref fails: emit a diagnostic in phase ‘resolve’, record the
failure, and mark dependent evaluations to resolve to N[missing_binding] or N[missing_policy]
when reached. Bridge endpoint patterns are not required to resolve to full frames here.
#### 16.6.2 Phase 2 — Resolve Evaluation Context
Construct active context from bundle frame,
evaluator panel, resolution policy, time, active assumptions, baselines, anchors, evidence, and
evidence relations.
The bundle frame must be a full FrameNode before direct claim evaluation. FramePatternNodes in BridgeNode.from/to, baseline-local frames, and DeclarationExprNode.within may remain partial unless direct evaluation requires them.
#### 16.6.3 Phase 3 — Initialize or Reuse Baseline Service
Baseline timing is defined relative
to the session and the effective step context.
For each baseline b:
fixed. With shared_state=true, the cache key is (session_id, baseline_id). A fixed baseline resolves once per session, either at explicit session initialization or at first use. If resolution succeeds, later step-local time changes, frame overrides, or history changes do not invalidate the
cached value for that session. If resolution has not yet occurred, the first step that triggers it
determines the context against which it is fixed.
fixed with shared_state=false. The cache key is (session_id, step_id, baseline_id). Each step
behaves as a fresh fixed-baseline context. A fixed baseline may therefore take different values
in different steps of the same session.
on_reference. No session-wide cache is assumed. The baseline is resolved each time a referencing claim is evaluated, under the current effective step context plus the baseline-local frame
overlay. Implementations may memoize only when the full effective context is equivalent.
tracked.
The baseline resolves as a time-indexed object over the session/step time context.
tracked is required for kind=moving.
Additional rules:
- If a baseline-local frame overlay cannot be resolved when required, dependent claim evaluation resolves locally to N[out_of_scope] or N[missing_policy], with a baseline-phase diagnostic.
- Cyclic baseline dependency yields N[undefined_term] plus a baseline diagnostic.
- A tracked baseline returning a trajectory requires a declared reduction or comparison
rule for any downstream scalar comparison; absent one, the dependent claim yields
N[undefined_term].
#### 16.6.4 Phase 4 — Evaluate Adequacy Assessments
Each AdequacyAssessment is evaluated
independently: resolve method, resolve basis, determine or compute score, compare to threshold.
Rules: method unresolved →N[missing_binding]. Basis ref unresolved →N[missing_binding].
Score present →attested output.
Score absent →method must compute it.
Score=N →
N[not_yet_applicable].
If executable method and declared score materially disagree →
B[method_conflict].
For multiple assessments per anchor/task: aggregate under adequacy_policy. No policy with
multiple assessments →N[missing_policy].
Circularity rule: if an assessment’s basis references a claim that transitively depends on the
assessment, result is N[circular_dependency].
License
task
resolution:
claim.annotations[‘license_task’]
>
evaluator-policy
mapping
>
ctx.frame.task.
Individual adequacy: aggregated score >= threshold →T; score < threshold →F[threshold_not_met];
score=N or no record →N[not_yet_applicable].
Joint adequacy:
required when any used anchor lists another via requires_joint_with, or
a matching JointAdequacy exists for the active anchor set and license task.
Missing →
N[missing_joint_adequacy]; failed →F[joint_inadequacy]; score=N →N[not_yet_applicable].
Exact-set matching: joint adequacy lookup against the exact, order-insensitive, deduplicated
anchor set from Claim.usesAnchors. Match requires exactly that set and the same task.
Overall license (operational severity, not propositional conjunction): F if any required component
is F; else B if any is B; else N if any is N; else T.
License results do not automatically override world-claim truth.
#### 16.6.5 Phase 5 — Materialize Declared Evidence Views Per Claim
For each claim: resolve claim.refs to explicit
evidence items; collect declared EvidenceRelations; compute a ClaimEvidenceView. crossConflictScore = maximum conflict score among relevant conflicts relations. completenessSummary
= minimum completeness over relevant evidence items. This phase handles declared evidence
structure only. The declared evidence graph is a per-claim artifact; evaluator-specific policy only enters during support synthesis (Phase 7).
#### 16.6.6 Phase 6 — Evaluate Claim Truth (Per Evaluator)
For each evaluator in the panel,
evaluate each claim independently.
Notes: NoteExprNode is non-evaluable. Receives no EvalNode. Excluded from block folding.
Term resolution: BaselineRefTermNode →baseline service. UnboundRefTermNode →tagged
unbound object. NullTermNode →tagged null object. Plain symbols remain symbolic unless a
handler interprets them.
Expression dispatch:
- PredicateExpr →delegate evalPredicate. Absent handler: N[missing_binding].
- DynamicExpr →delegate evalDynamic. Absent handler: N[missing_binding].
- CausalExpr →delegate evalCausal. Absent handler: N[missing_binding].
- EmergenceExpr →delegate evalEmergence. Absent handler: N[missing_binding].
- DeclarationExpr →delegate evalDeclaration if available. Default: T if within absent; T/F by
frame match if within is FramePattern; inherit expression truth if within is Expr.
- JudgedExpr →two-stage: evaluate inner expression, then delegate to criterion binding with
innerTruth. Absent handler: N[missing_binding].
- LogicalExpr →handled internally by recursion and four-valued truth tables.
Logical reason derivation: If logical composition yields B or N: if one child reason uniquely
determines the outcome, inherit it; otherwise use logical_composition and record contributing
child reasons in diagnostics.
#### 16.6.7 Phase 7 — Synthesize Support (Per Evaluator)
After truth evaluation per evaluator, build final support from ClaimEvidenceView, truth-core provenance, and declared evidence
relations.
Default support policy (replaceable by declared evidence policy):
declaration claims with no evidence → inapplicable; E(claim)=∅ → absent; any relevant conflicts
relation present → conflicted; no conflict but some evidence incomplete or internally conflicted
→ partial; otherwise → supported.
Non-evaluable claims such as NoteExpr do not enter support synthesis.
Inference of conflicts is off by default. Only declared EvidenceRelation(kind=conflicts) entries
count.
Confidence assigned by assessConfidence if provided, otherwise left unset.
Provenance =
union(truthCore.provenance, support.provenance, [evaluator.id]).
#### 16.6.8 Phase 8 — Aggregate Claim Results
Apply the bundle’s resolution policy to the per-evaluator eval maps to produce aggregate EvalNode for each claim.
For built-in resolution policies, aggregate EvalNode fields are determined as follows:
- **truth:** per the policy’s truth rule (Section 8.3).
- **reason:** inherited unique reason where possible; otherwise the policy-specific reason (e.g. evaluator_conflict for paraconsistent_union).
- **support:**
  - paraconsistent_union: conflicted if any evaluator returned conflicted or if aggregate truth is B[evaluator_conflict]; else partial if any returned partial; else supported if any returned supported; else inapplicable if all returned inapplicable; else absent.
  - single: copy selected evaluator.
  - priority_order: copy selected evaluator.
- **confidence:**
  - single / priority_order: copy selected evaluator.
  - paraconsistent_union: unset by default unless an implementation or policy binding defines a built-in aggregation rule.
- **provenance:** union of participating evaluator provenance; add policy provenance when the policy is delegated.
#### 16.6.9 Phase 9 — Fold Blocks
For each evaluator, fold the claims in the block using Limnalis conjunction. Then aggregate those evaluator-local block truths under the resolution policy.
Excludes non-evaluable notes. Empty evaluable set →N. Source order preserved for traceability.
For block aggregation under the adjudicated resolution policy, the resolution binding receives
synthetic EvalNodes whose truth is the evaluator-local block truth, whose support is inapplicable,
and whose provenance includes the evaluator id and block id. This prevents implementers from
making incompatible assumptions about claim-level versus block-level adjudication.
#### 16.6.10 Phase 10 — Execute Transport Queries
Transport is step-scoped. For each query:
locate claim result and bridge; check claim frame matches bridge.from pattern; determine transport mode from bridge.transport.mode.
- metadata_only: return metadata_only with preserve/lose/gain/risk metadata. This is the
declared transport mode.
- pattern_only (status): returned when a bridge has no transport handler and no explicit
transport mode was declared, or when a legacy bridge is queried.
Distinct from metadata_only: pattern_only means no handler was present; metadata_only means the declared
mode is metadata-only.
- preserve: check preconditions and semantic_requirements ∩lose = ∅. If satisfied, copy
source aggregate eval. Otherwise N[transport_loss] or N[transport_precondition].
- degrade: attempt preserve; on failure, apply degradation rules.
- remap_recompute:
map claim via claim_map, complete destination frame, evaluate
mapped claim under destination evaluators and resolution policy.
A bridge without a transport handler that is queried for truth returns N[transport_missing].
### 16.7 Core Recursive Procedures
evaluate_claim(claim, ctx, evaluators, services):
if claim.expr is NoteExpr: return ClaimResult(eval=None, ...)
license = evaluate_license(claim, ctx, services)
per_eval = {}
for ev in evaluators:
truthCore = eval_expr(claim.expr, claim, ctx, ev, services)
evidenceView = lookup_evidence_view(claim, truthCore, ctx)
supportCore = assess_support(claim, evidenceView, truthCore,
ctx, ev, services)
per_eval[ev.id] = merge(truthCore, supportCore, ev.id)
aggregate = apply_resolution_policy(per_eval,
ctx.resolutionPolicy, ctx, services)
return ClaimResult(claimId, per_eval, aggregate, license,
diagnostics)
### 16.8 Failure Modes
Hard Validation Failures (may abort evaluation): malformed canonical AST; missing bundle
frame or evaluator panel; duplicate ids in the same bundle-local namespace.
Localized Evaluation Failures (degrade locally): missing binding for one claim →N[missing_binding];
unresolved baseline criterion; failed license lookup for one claim; unsupported criterion binding
for one judged expression; unresolved projection reuse →N[unsafe_projection]; missing transport handler for one bridge query; circular adequacy dependency →N[circular_dependency].
### 16.9 Conformance Rules
A Limnalis evaluator is conformant to v0.2.2 if it:
1. Consumes the canonical AST or an equivalent normalized representation.
2. Preserves the normative phase order.
3. Respects four-valued truth functions for logical composition and block folding.
4. Keeps bridge endpoints as patterns unless actual evaluation requires a full frame.
5. Resolves baseline timing according to evaluationMode relative to the session.
6. Keeps anchor licensing distinct from world-claim truth by default.
7. Materializes evidence conflict before support assignment.
8. Requires reason codes for B and N.
9. Does not silently turn missing bindings or unresolved patterns into F.
10. Evaluates claims per evaluator before applying the resolution policy.
11. Folds blocks per evaluator before aggregating across evaluators.
12. Applies transport modes as declared.
13. Evaluates adequacy assessments before dependent claims within the step.
14. Respects the circularity rule for adequacy basis references.
## 17. Conformance Corpus
The conformance corpus is a set of spec fixtures, not tutorial examples. Each case is designed
to pin down one or two semantics cleanly and to be machine-checkable once a parser and prototype evaluator exist. The full matrix with canonical source is maintained in the companion
spreadsheet. Machine-readable representations (YAML and JSON) are maintained alongside it
and validate cleanly against the fixture corpus schema (0 errors).
### 17.1 Corpus Conventions
All bindings under test://… are deterministic fixtures with stated outputs.
Fixture bindings (deterministic):
- test://eval/declaration_v1 — default declaration semantics from reference evaluator.
- test://eval/atoms_v1 — p=T, q=T, b=B[source_conflict], n=N[undefined_term].
- test://eval/baseline_v1 — T when referenced baseline resolves successfully.
- test://eval/auth_truth_v1 — T for all world predicates (isolates licensing from truth).
- test://eval/grid_v1 — overload(line_B)=T; causal c2=B[source_conflict]; c3=T.
- test://eval/jwt_gateway_v1 — T for c1-c4 in B2; support from evidence policy.
- test://policy/auth_access_v3 — criterion binding for B2 c3; returns T under fixture.
- test://policy/jwt_support_v1 — reference-default support policy for v0.2.2: conflicted
if any relevant conflicts relation present; otherwise partial if any relevant evidence has
completeness < 1 or internal_conflict > 0; otherwise supported.
- test://bridge/pattern_only — no transportClaim handler →metadata_only.
- test://bridge/pass_through — trivial transportClaim handler; preserves truth/provenance.
- test://bridge/degrade_v1 — transport handler implementing degrade mode with default
degradation rules.
- test://bridge/remap_v1 — transport handler implementing remap_recompute; remaps
source claim to destination frame and re-evaluates.
- test://baseline/const10 — scalar 10.
- test://baseline/series_9_10_11 — tracked trajectory [9,10,11] over active time index.
- test://baseline/reactive_margin_zero — reactive-margin zero reference used in B1.
- test://baseline/by_context_v1 — context-sensitive baseline: returns 10 under step context (t1, regime=nominal) and 20 under step context (t2, regime=stress).
- test://eval/adversarial_v1 — returns F for all predicates (adversarial evaluator fixture).
- test://eval/audit_n_v1 — returns N[missing_evidence] for all predicates (audit evaluator
with no evidence).
- test://eval/model_true_v1 — returns T for all predicates (primary model evaluator).
- test://eval/fallback_false_v1 — returns F for all predicates (fallback evaluator).
- test://resolution/adjudicated_v1 — adjudication binding. Input: keyed map { evaluator_id →EvalNode }. Output: aggregate EvalNode. Rule set: if primary.truth=T and adversarial.truth=F, return { truth=B, reason=evaluator_conflict, support=conflicted, provenance=union(inputs)+binding }; if all listed member truths agree, return the agreed truth;
when truths agree, merge support conservatively (conflicted > partial > supported > inapplicable > absent); provenance is the union of member provenances plus the adjudication
binding. For block aggregation under adjudicated, the resolution binding receives synthetic
EvalNodes whose truth is the evaluator-local block truth, whose support is inapplicable, and
whose provenance includes the evaluator id and block id.
- test://adequacy/recompute_v1 — executable adequacy method; recomputes score to 0.88
(disagrees with declared 0.95 beyond tolerance).
- test://adequacy/compute_pass_v1 — executable adequacy method; computes score and
returns passing result (used for score-omitted assessment path).
- test://eval/judged_inner_v1 — returns inner expression truth for predicate evaluation;
criterion binding passes through inner truth as judged result.
### 17.2 Track A — Core Semantics
Cases A1–A7 remain from v0.2 with minor updates for evaluator panel syntax. Cases A8–A14
are new.
A1. Resolved shorthand frame — unchanged from v0.2 except evaluator →evaluators list +
single resolution policy. Expected results unchanged.
A2. Unresolved shorthand frame — unchanged semantics. Expected results unchanged.
A3. Logical composition and block folding — unchanged semantics. Expected results unchanged. c6 remains the B∧N=F exercise.
A4. Baseline modes: fixed, on_reference, tracked, invalid — unchanged claim-level results.
Baseline timing semantics now explicitly session-relative. Expected results unchanged for singlestep implicit session.
A5.
Evidence conflict vs partial support — unchanged semantics.
Expected results unchanged.
A6. Individual adequacy, joint adequacy, and missing joint adequacy — updated to use
AdequacyAssessment with explicit producer.
Expected claim and license results unchanged.
Adequacy records now carry producer field.
A7.
Bridge transport: pattern-only vs transported — unchanged for metadata_only and
pass_through modes.
A8.
Multi-evaluator conflict (new).
Pins down paraconsistent_union resolution and perevaluator-first block folding.
Bundle declares two evaluators: ev_primary (uses test://eval/atoms_v1: p=T) and ev_adversarial
(uses test://eval/adversarial_v1: p=F). Resolution policy: paraconsistent_union.
Expected claim evals:
- c1 (predicate p):
per_evaluator = {ev_primary:
T, ev_adversarial:
F}; aggregate =
B[evaluator_conflict] / conflicted.
- c2 (predicate q):
per_evaluator = {ev_primary:
T, ev_adversarial:
F}; aggregate =
B[evaluator_conflict] / conflicted.
Expected block evals:
- block(local): per_evaluator = {ev_primary: T∧T=T, ev_adversarial: F∧F=F}; aggregate =
paraconsistent_union(T,F) = B[evaluator_conflict].
Key result: blocks are folded per evaluator first (T and F), then aggregated (B). Not: aggregated
claim truths (B∧B=B) then folded.
A9. Priority-order resolution (new). Pins down priority_order fallback behavior.
Bundle declares three evaluators: ev_audit (returns N[missing_evidence]), ev_model (returns
T), ev_fallback (returns F). Resolution policy:
priority_order, order:
[ev_audit, ev_model,
ev_fallback].
Expected:
- c1: per_evaluator = {ev_audit: N, ev_model: T, ev_fallback: F}; aggregate = T (first non-N
is ev_model).
A10. Transport truth modes (updated). Pins down preserve, degrade, remap_recompute,
and the empty-semantic_requirements warning.
Bundle declares one claim c1=T with semantic_requirements=[phase_angle].
Additionally,
c_warn is predicate p with semantic_requirements=[]. Three bridges plus one lint-triggering
bridge:
- b_preserve: transport.mode=preserve; lose=[switching_order]; c1.semantic_requirements
∩lose = ∅ →preserved. Expected: status=preserved, dstAggregate=T.
- b_degrade:
transport.mode=degrade; lose=[phase_angle]; c1.semantic_requirements ∩
lose ≠∅ →degraded. Expected: status=degraded, dstAggregate=N[transport_loss].
- b_remap:
transport.mode=remap_recompute;
claim_map=test://bridge/remap_v1.
Expected: status=transported, dstAggregate=result of re-evaluation in destination frame.
- b_warn:
transport.mode=preserve; lose=[phase_angle].
Transport query on c_warn:
status=preserved, dstAggregate=T (semantic_requirements is empty so ∩lose = ∅ trivially).
Expected diagnostic: warning, code=lint.transport.semantic_requirements_empty,
phase=transport, subject=c_warn.
A11.
Session-based baseline timing (updated).
Pins down fixed vs on_reference and
shared_state with deterministic expected outputs.
Bundle declares:
b_fixed (evaluation_mode=fixed,
criterion=test://baseline/by_context_v1),
b_step
(evaluation_mode=on_reference,
criterion=test://baseline/by_context_v1),
c_fixed
(matches_baseline(sensor_A, |0:b_fixed|)), c_step (matches_baseline(sensor_A, |0:b_step|)).
Fixture: test://baseline/by_context_v1 returns 10 under step context (t1, regime=nominal) and
20 under step context (t2, regime=stress). sensor_A is fixed at 10. test://eval/baseline_v1 returns
T when sensor_A matches the resolved baseline and F otherwise.
Session s_shared (shared_state=true): step s1 (time=t1, frame_override @regime=nominal),
step s2 (time=t2, frame_override @regime=stress).
Expected s_shared: s1: b_fixed=10, b_step=10, c_fixed=T, c_step=T. s2: b_fixed=10 (cached),
b_step=20 (re-resolved), c_fixed=T, c_step=F.
Session s_isolated (shared_state=false): same two step contexts.
Expected s_isolated: s1: b_fixed=10, b_step=10, c_fixed=T, c_step=T. s2: b_fixed=20 (reinitialized), b_step=20, c_fixed=F, c_step=F.
Diagnostics: none required.
A12. Adequacy method conflict, circularity, and missing policy (updated). Pins down
assessment-level semantics and lint rules 24–25.
Bundle declares anchor a_model with two assessments for task=prediction:
- aa1: producer=sim_team, score=0.95, threshold=0.90, method=test://adequacy/recompute_v1.
Method recomputes to 0.88 (disagrees with declared 0.95 beyond tolerance). Expected:
B[method_conflict].
- aa2:
producer=audit_team, threshold=0.90, method=test://adequacy/compute_pass_v1
(score omitted; method computes). Expected: T.
With adequacy_policy: paraconsistent_union, aggregate = B (from method_conflict).
Additionally, anchor a_circular with one assessment whose basis references a claim that depends on a_circular’s adequacy. Expected: N[circular_dependency]. Expected diagnostic: error,
code=lint.adequacy.circular_basis, phase=license, subject=aa_circular.
Additionally,
anchor
a_nopolicy
with
two
assessments
for
task=prediction
and
no
adequacy_policy declared.
Expected: adequacy(a_nopolicy, prediction) = N[missing_policy].
Expected diagnostic: warning, code=lint.adequacy.missing_policy_multi_assessment, phase=license,
subject=a_nopolicy.
A13. Core JudgedExpr (new). Pins down two-stage judged evaluation.
Bundle declares c1:
safe(grid_state)
judged_by
test://eval/judged_inner_v1.
The fixture evaluates the inner predicate safe(grid_state) to T, then the criterion binding receives
innerTruth=T and returns T.
Additionally, c2 uses an unresolved criterion. Expected: N[missing_binding].
A14. Adjudicated resolution (new). Pins down the adjudicated escape hatch at both claim
and block level.
Bundle declares two evaluators: ev_primary (uses test://eval/atoms_v1) and ev_adversarial (uses
test://eval/adversarial_v1). Resolution policy: adjudicated, binding=test://resolution/adjudicated_v1.
Claims: c1 is predicate p; c2 is logical expression (b AND n).
Expected per-evaluator results. Using existing fixtures: atoms_v1 gives p=T, b=B[source_conflict],
n=N[undefined_term]; adversarial_v1 gives all predicates F.
- c1: per_evaluator = {ev_primary: T/absent, ev_adversarial: F/absent}.
Adjudicated aggregate = B[evaluator_conflict]/conflicted (primary=T, adversarial=F triggers the conflict
rule).
- c2: per_evaluator = {ev_primary: F/absent (B∧N=F), ev_adversarial: F/absent}. Adjudicated aggregate = F/absent (both agree on F).
Expected block result.
Per-evaluator block fold first:
block(local).ev_primary = T∧F = F;
block(local).ev_adversarial = F∧F = F. Adjudication receives synthetic EvalNodes with truth=F,
support=inapplicable. Both agree →block(local).aggregate = F.
Key result: the adjudicator is not merely another truth combiner but a binding that consumes
full per-evaluator results and produces a full aggregate result. Block-level adjudication operates
on synthetic EvalNodes, not raw truth values.
### 17.3 Track B — Domain Bundles
B1.
Grid contingency — updated to use evaluators list + single resolution policy.
Anchor
adequacy updated to AdequacyAssessment with explicit producer. Expected results unchanged.
B2. JWT access / adequacy — updated to use evaluators list + single resolution policy. Expected results unchanged. Support grounding for c3 via test://policy/jwt_support_v1 remains
normatively fixed.
### 17.4 Remaining Open Questions
Transport truth modes coverage. A10 is the only case exercising preserve, degrade, and
remap_recompute truth-bearing transport. B1 exercises metadata_only. A second case exercising remap_recompute with a non-trivial destination evaluator panel would strengthen coverage.
Session evaluation coverage. A11 is the only case exercising session semantics. A second case
exercising claim_subset, session-scoped transport queries, or tracked baselines across steps
would strengthen coverage.
AST pressure points. All four previously open AST decisions (ResolutionPolicyNode, TransportNode, AdequacyAssessmentNode.score, ClaimResult/BlockResult per_evaluator maps) are
now settled. See Section 19.
## 18. JSON Schema Package
The schema package drafts the JSON Schema layer directly from the conformance corpus rather
than from prose alone. It consists of four artifacts:
- limnalis_ast_schema — canonical AST schema for normalized bundles and all node families.
- limnalis_conformance_result_schema — expected-result schema used by conformance
cases, defining the shape of EvalSnapshot, ClaimExpectation, BlockExpectation, TransportExpectation, SessionExpectation, StepExpectation, and DiagnosticExpectation.
- limnalis_fixture_corpus_schema — top-level schema for the machine-readable fixture
corpus (fixtures, cases, AST decisions, metadata).
- limnalis_schema_validation_report — validation report confirming the current fixture
corpus validates cleanly (0 errors).
### 18.1 Discriminated Unions
ResolutionPolicyNode and TransportNode are modeled as discriminated unions using JSON
Schema’s if/then/not conditional validation:
ResolutionPolicyNode discriminates on kind:
- single: members required (length=1); order and binding forbidden.
- paraconsistent_union: members required (length≥1); order and binding forbidden.
- priority_order: order required (length≥1); members optional (if present, must equal same
set as order); binding forbidden.
- adjudicated: members required (length≥1); binding required; order forbidden.
TransportNode discriminates on mode:
- metadata_only: claimMap, truthPolicy, dstEvaluators, dstResolutionPolicy all forbidden.
- preserve: claimMap, dstEvaluators, dstResolutionPolicy forbidden; truthPolicy and preconditions optional.
- degrade: same as preserve.
- remap_recompute: claimMap required; truthPolicy forbidden; preconditions, dstEvaluators,
dstResolutionPolicy optional.
### 18.2 Conformance Result Schema
The conformance result schema defines the shape that evaluator output must match for corpus
comparison. Key types:
- EvalSnapshot: truth (required), reason, support, confidence, provenance.
- ClaimExpectation: per_evaluator map + aggregate EvalSnapshot + optional license. Conditional rule: if aggregate is present, per_evaluator is required.
- BlockExpectation: per_evaluator map (string→TruthValue) + aggregate TruthValue. Both
required.
- TransportExpectation:
status (required) + optional sourceAggregate, dstAggregate,
per_evaluator.
- SessionExpectation/StepExpectation: hierarchical session→step→claims/blocks/transports
structure.
### 18.3 Constraints Beyond JSON Schema
The following semantic constraints are intentionally left to evaluator-level or custom validation
because JSON Schema cannot express them cleanly:
- Exact-set equality for joint adequacy anchor matching.
- Uniqueness of ids across bundle-local namespaces.
- Equality between priority_order.members and priority_order.order.
- Cross-node circular-dependency detection in adequacy basis chains.
The corpus, not the schema alone, remains the arbiter of which fields are conditionally required.
## 19. Settled AST Decisions
These four AST decisions are treated as settled for schema drafting, based on the conformance
corpus (A1–A14, B1–B2).
ResolutionPolicyNode — settled. Discriminated union on kind. Corpus support: A8, A9, A14.
TransportNode — settled. Discriminated union on mode. Corpus support: A7, A10, B1.
AdequacyAssessmentNode.score — settled. Optional field. When present, treated as attested
output of method. When absent, method must compute it. When method and declared score
disagree, result is B[method_conflict].
Unresolved method always yields N[missing_binding]
regardless of score presence. Corpus support: A12, B1, B2.
ClaimResult / BlockResult per_evaluator maps — settled. Required for evaluable claims
and blocks. Omitted for NoteExpr claims. Keys must match effective evaluator panel. Corpus
support: A8, A9, A14, B1, B2.
Limnalis v0.2.2 — end of specification, grammar/AST appendix, reference evaluator, conformance corpus, and schema package

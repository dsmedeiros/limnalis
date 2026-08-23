# Limnalis v0.2.2 — Conformance matrix

Updated corpus snapshot with A14 adjudicated resolution, settled AST pressure points, and machine-readable fixture artifacts.

## Overview

- Track A: A1–A14 core semantics.
- Track B: B1–B2 domain bundles.
- Deterministic fixtures: 23.
- Settled AST decisions: ResolutionPolicyNode, TransportNode, AdequacyAssessmentNode.score, ClaimResult/BlockResult per_evaluator maps.

## Cases

### A1 — Resolved shorthand frame

**Track:** Core semantics  
**Focus:** shorthand_frame, frame_resolution, declaration

**Canonical source**
```limnalis
bundle A1_resolved_frame {
  frame @PowerGrid:ACLoadFlow::contingency;

  evaluator ev0 {
    kind model;
    binding test://eval/declaration_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  meta {
    c1: declare Nminus1 as idealization within @{system=PowerGrid, namespace=ACLoadFlow, regime=contingency};
    c2: declare Nminus1 as idealization within @{system=PowerGrid, namespace=ACLoadFlow, task=planning};
  }
}
```

**AST / normalization expectations**
- bundle.frame -> FramePatternNode
- frame resolver completes bundle frame to full FrameNode before direct evaluation
- c1, c2 -> DeclarationExprNode

**Evaluation expectations**
```text
Claims
• c1 = T / inapplicable
• c2 = F / inapplicable

Blocks
• block(meta) = F
```

**Diagnostics**
- info: frame_pattern_completed

### A2 — Unresolved shorthand frame

**Track:** Core semantics  
**Focus:** shorthand_frame, frame_resolution_failure

**Canonical source**
```limnalis
bundle A2_unresolved_frame {
  frame @PowerGrid:ACLoadFlow::contingency;

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  local {
    c1: p;
  }
}
```

**AST / normalization expectations**
- bundle.frame remains FramePatternNode
- no full FrameNode available for direct evaluation

**Evaluation expectations**
```text
No claim or block evals.
Evaluation aborts in phase 2.
```

**Diagnostics**
- error: frame_unresolved_for_evaluation

### A3 — Logical composition and block folding

**Track:** Core semantics  
**Focus:** logical_expr, block_folding, B_and_N_equals_F

**Canonical source**
```limnalis
bundle A3_logic_block {
  frame {
    system Test;
    namespace Logic;
    scale unit;
    task check;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  local {
    c1: b;
    c2: n;
  }

  systemic {
    c3: p;
    c4: b;
  }

  meta {
    c5: (p AND b);
    c6: (b AND n);
  }
}
```

**AST / normalization expectations**
- b, n, p in expression position -> zero-arity PredicateExprNode
- c5, c6 -> LogicalExprNode
- local/systemic/meta -> ClaimBlockNode

**Evaluation expectations**
```text
Claims
• c1 = B[source_conflict] / absent
• c2 = N[undefined_term] / absent
• c3 = T / absent
• c4 = B[source_conflict] / absent
• c5 = B[source_conflict] / absent
• c6 = F / absent

Blocks
• block(local) = F
• block(systemic) = B
• block(meta) = F
```

**Diagnostics**
- info: logical_composition (c6)

### A4 — Baseline modes

**Track:** Core semantics  
**Focus:** baseline_modes, tracked_validation

**Canonical source**
```limnalis
bundle A4_baseline_modes {
  frame {
    system Test;
    namespace Baseline;
    scale service;
    task compare;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/baseline_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  baseline b_fixed {
    kind point;
    criterion ref test://baseline/const10;
    frame @{system=Test, namespace=Baseline, regime=nominal};
    evaluation_mode fixed;
  }

  baseline b_lazy {
    kind point;
    criterion ref test://baseline/const10;
    frame @{system=Test, namespace=Baseline, regime=nominal};
    evaluation_mode on_reference;
  }

  baseline b_tracked {
    kind moving;
    criterion ref test://baseline/series_9_10_11;
    frame @{system=Test, namespace=Baseline, regime=nominal};
    evaluation_mode tracked;
  }

  baseline b_invalid {
    kind moving;
    criterion ref test://baseline/series_9_10_11;
    frame @{system=Test, namespace=Baseline, regime=nominal};
    evaluation_mode fixed;
  }

  local {
    c1: matches_baseline(sensor_A, |0:b_fixed|);
    c2: matches_baseline(sensor_A, |0:b_lazy|);
    c3: within_band(sensor_A, |0:b_tracked|);
    c4: within_band(sensor_A, |0:b_invalid|);
  }
}
```

**AST / normalization expectations**
- |0:*| -> BaselineRefTermNode
- b_invalid is syntactically valid but semantically invalid

**Evaluation expectations**
```text
Claims
• c1 = T / absent
• c2 = T / absent
• c3 = T / absent
• c4 = N[undefined_term] / absent

Blocks
• block(local) = N

Baseline states
• b_fixed = ready
• b_lazy = deferred
• b_tracked = ready
• b_invalid = unresolved
```

**Diagnostics**
- error: baseline_mode_invalid (b_invalid)

### A5 — Evidence conflict vs partial support

**Track:** Core semantics  
**Focus:** evidence_conflict, support_classification

**Canonical source**
```limnalis
bundle A5_evidence_conflict {
  frame {
    system Test;
    namespace Evidence;
    scale service;
    task assess;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  evidence e1 {
    kind measurement;
    binding test://evidence/e1;
    completeness 1.0;
  }

  evidence e2 {
    kind measurement;
    binding test://evidence/e2;
    completeness 1.0;
  }

  evidence e3 {
    kind measurement;
    binding test://evidence/e3;
    completeness 0.60;
    internal_conflict 0.10;
  }

  evidence_relation er12 {
    lhs e1;
    rhs e2;
    kind conflicts;
    score 0.80;
  }

  local {
    c1: p refs [e1, e2];
    c2: q refs [e3];
  }
}
```

**AST / normalization expectations**
- claim refs resolve to EvidenceNode ids
- er12 -> EvidenceRelationNode(kind=conflicts)

**Evaluation expectations**
```text
Claims
• c1 = T / conflicted
• c2 = T / partial

Blocks
• block(local) = T
```

**Diagnostics:** none required.

### A6 — Individual and joint adequacy

**Track:** Core semantics  
**Focus:** individual_adequacy, joint_adequacy, exact_set_match

**Canonical source**
```limnalis
bundle A6_anchor_licenses {
  frame {
    system Auth;
    namespace Fixture;
    scale service;
    task access;
    regime steady;
  }

  evaluator ev0 {
    kind institution;
    binding test://eval/auth_truth_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  anchor a_stateless {
    term symbol stateless_session;
    subtype idealization;
    status active;

    adequacy {
      task access;
      producer sim_team;
      score 0.97;
      threshold 0.90;
      method test://method/a_stateless_access;
    }

    adequacy {
      task revocation;
      producer sim_team;
      score 0.40;
      threshold 0.90;
      method test://method/a_stateless_revocation;
    }
  }

  anchor a_clock {
    term symbol bounded_clock_skew;
    subtype idealization;
    status active;

    adequacy {
      task access;
      producer sim_team;
      score 0.95;
      threshold 0.90;
      method test://method/a_clock_access;
    }
  }

  anchor a_cache {
    term symbol cache_visibility;
    subtype proxy;
    status active;
    requires_joint_with [a_stateless];

    adequacy {
      task access;
      producer sim_team;
      score 0.93;
      threshold 0.90;
      method test://method/a_cache_access;
    }
  }

  joint_adequacy ja_access {
    anchors [a_stateless, a_clock];
    assessment {
      task access;
      producer sim_team;
      score 0.92;
      threshold 0.90;
      method test://method/ja_access;
    }
  }

  local {
    c1: gateway_allows(tok_A) uses [a_stateless] annotations {"license_task": "access"};
    c2: gateway_allows(tok_A) uses [a_stateless, a_clock] annotations {"license_task": "access"};
    c3: revocation_visible(tok_A) uses [a_stateless] annotations {"license_task": "revocation"};
    c4: cache_consistent(tok_A) uses [a_stateless, a_cache] annotations {"license_task": "access"};
  }
}
```

**AST / normalization expectations**
- uses [...] -> ClaimNode.usesAnchors
- annotations["license_task"] is reserved
- JointAdequacy exact-set matching uses claim-local usesAnchors set

**Evaluation expectations**
```text
Claims
• c1 = T / absent ; license = T
• c2 = T / absent ; license = T
• c3 = T / absent ; license = F[threshold_not_met]
• c4 = T / absent ; license = N[missing_joint_adequacy]

Blocks
• block(local) = T
```

**Diagnostics**
- warning: missing_joint_adequacy (c4)

### A7 — Bridge transport: metadata_only vs preserve

**Track:** Core semantics  
**Focus:** bridge_patterns, transport_plumbing

**Canonical source**
```limnalis
bundle A7_bridge_transport {
  frame {
    system Test;
    namespace Scope;
    scale micro;
    task ops;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  bridge b_pattern {
    from @{system=Test, namespace=Scope, scale=micro, task=ops};
    to @{system=Test, namespace=Scope, scale=macro, task=planning};
    via test://bridge/pattern_only;
    preserve [mass_balance];
    lose [phase_detail];
    transport {
      mode metadata_only;
    }
  }

  bridge b_exec {
    from @{system=Test, namespace=Scope, scale=micro, task=ops};
    to @{system=Test, namespace=Scope, scale=macro, task=planning, regime=nominal};
    via test://bridge/pass_through;
    preserve [mass_balance];
    lose [phase_detail];
    transport {
      mode preserve;
    }
  }

  local {
    c1: p;
  }
}
```

**AST / normalization expectations**
- bridge.from and bridge.to remain FramePatternNode
- transport block -> TransportNode

**Evaluation expectations**
```text
Claims
• c1 = T / absent

Blocks
• block(local) = T

Transports
• q1: metadata_only
• q2: preserved, dst=T
```

**Diagnostics:** none required.

### A8 — Multi-evaluator conflict

**Track:** Core semantics  
**Focus:** multi_evaluator, paraconsistent_union, block_fold_order

**Canonical source**
```limnalis
bundle A8_multi_evaluator_conflict {
  frame {
    system Test;
    namespace Panel;
    scale service;
    task review;
    regime nominal;
  }

  evaluator ev_primary {
    kind model;
    role primary;
    binding test://eval/atoms_v1;
  }

  evaluator ev_adversarial {
    kind model;
    role adversarial;
    binding test://eval/adversarial_v1;
  }

  resolution_policy rp_panel {
    kind paraconsistent_union;
    members [ev_primary, ev_adversarial];
  }

  local {
    c1: p;
    c2: q;
  }
}
```

**AST / normalization expectations**
- two EvaluatorNodes
- ResolutionPolicyNode(kind=paraconsistent_union)

**Evaluation expectations**
```text
Claims
• c1 = B[evaluator_conflict] / conflicted
• c2 = B[evaluator_conflict] / conflicted

Blocks
• block(local) = B
```

**Diagnostics:** none required.

### A9 — Priority-order resolution

**Track:** Core semantics  
**Focus:** priority_order, first_non_N

**Canonical source**
```limnalis
bundle A9_priority_order {
  frame {
    system Test;
    namespace Priority;
    scale service;
    task review;
    regime nominal;
  }

  evaluator ev_audit {
    kind audit;
    role audit;
    binding test://eval/audit_n_v1;
  }

  evaluator ev_model {
    kind model;
    role primary;
    binding test://eval/model_true_v1;
  }

  evaluator ev_fallback {
    kind model;
    role auxiliary;
    binding test://eval/fallback_false_v1;
  }

  resolution_policy rp_priority {
    kind priority_order;
    members [ev_audit, ev_model, ev_fallback];
    order [ev_audit, ev_model, ev_fallback];
  }

  local {
    c1: p;
  }
}
```

**AST / normalization expectations**
- ResolutionPolicyNode(kind=priority_order) with explicit order

**Evaluation expectations**
```text
Claims
• c1 = T / absent

Blocks
• block(local) = T
```

**Diagnostics:** none required.

### A10 — Transport truth modes

**Track:** Core semantics  
**Focus:** preserve, degrade, remap_recompute, semantic_requirements

**Canonical source**
```limnalis
bundle A10_transport_truth_modes {
  frame {
    system Test;
    namespace Scope;
    scale micro;
    task ops;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  bridge b_preserve {
    from @{system=Test, namespace=Scope, scale=micro, task=ops};
    to @{system=Test, namespace=Scope, scale=macro, task=planning, regime=nominal};
    via test://bridge/pass_through;
    preserve [mass_balance];
    lose [switching_order];
    transport {
      mode preserve;
    }
  }

  bridge b_degrade {
    from @{system=Test, namespace=Scope, scale=micro, task=ops};
    to @{system=Test, namespace=Scope, scale=macro, task=planning, regime=nominal};
    via test://bridge/degrade_v1;
    preserve [mass_balance];
    lose [phase_angle];
    transport {
      mode degrade;
    }
  }

  bridge b_remap {
    from @{system=Test, namespace=Scope, scale=micro, task=ops};
    to @{system=Test, namespace=Scope, scale=macro, task=planning, regime=nominal};
    via test://bridge/remap_v1;
    preserve [mass_balance];
    lose [phase_detail];
    transport {
      mode remap_recompute;
      claim_map test://bridge/remap_v1;
    }
  }

  local {
    c1: p requires [phase_angle];
  }
}
```

**AST / normalization expectations**
- Claim.semanticRequirements populated from requires[...]
- Three BridgeNodes with distinct TransportNode.mode values

**Evaluation expectations**
```text
Claims
• c1 = T / absent

Blocks
• block(local) = T

Transports
• q_preserve: preserved, dst=T
• q_degrade: degraded, dst=N[transport_loss]
• q_remap: transported, dst=F
```

**Diagnostics:** none required.

### A11 — Session-based baseline timing

**Track:** Core semantics  
**Focus:** session_evaluation, fixed_vs_on_reference, temporal_observability

**Canonical source**
```limnalis
bundle A11_baseline_timing {
  frame {
    system Test;
    namespace Baseline;
    scale service;
    task compare;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/baseline_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  baseline b_fixed {
    kind point;
    criterion ref test://baseline/const10;
    frame @{system=Test, namespace=Baseline, regime=nominal};
    evaluation_mode fixed;
  }

  baseline b_step {
    kind point;
    criterion ref test://baseline/const10;
    frame @{system=Test, namespace=Baseline, regime=nominal};
    evaluation_mode on_reference;
  }

  local {
    c1: matches_baseline(sensor_A, |0:b_fixed|);
    c2: matches_baseline(sensor_A, |0:b_step|);
  }
}
```

**AST / normalization expectations**
- EvaluationRequest uses one session with two steps
- fixed baseline cache is session-scoped; on_reference resolves per step

**Evaluation expectations**
```text
Claims
• c1 = T / absent
• c2 = T / absent
```

**Diagnostics:** none required.

### A12 — Adequacy method conflict and circularity

**Track:** Core semantics  
**Focus:** adequacy_assessment, optional_score, method_conflict, circular_dependency

**Canonical source**
```limnalis
bundle A12_adequacy_assessment {
  frame {
    system Test;
    namespace Adequacy;
    scale service;
    task prediction;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/auth_truth_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  resolution_policy rp_adequacy {
    kind paraconsistent_union;
    members [sim_team, audit_team];
  }

  anchor a_model {
    term symbol model_fit;
    subtype idealization;
    status active;
    adequacy_policy rp_adequacy;

    adequacy {
      id aa1;
      task prediction;
      producer sim_team;
      score 0.95;
      threshold 0.90;
      method test://adequacy/recompute_v1;
    }

    adequacy {
      id aa2;
      task prediction;
      producer audit_team;
      threshold 0.90;
      method test://adequacy/compute_pass_v1;
    }
  }

  anchor a_circular {
    term symbol circular_fit;
    subtype idealization;
    status active;

    adequacy {
      id aa_circular;
      task prediction;
      producer audit_team;
      threshold 0.90;
      method test://adequacy/compute_pass_v1;
      basis [c_dependent];
    }
  }

  local {
    c1: model_ok(sample_1) uses [a_model] annotations {"license_task": "prediction"};
    c_dependent: dependent_claim(sample_1) uses [a_circular] annotations {"license_task": "prediction"};
  }
}
```

**AST / normalization expectations**
- AdequacyAssessmentNode.score is optional; aa2 exercises method-computed score path
- a_model.adequacy_policy aggregates same-task assessments
- basis [c_dependent] creates a circular adequacy dependency for a_circular

**Evaluation expectations**
```text
Claims
• c1 = T / absent ; license = B[adequacy_conflict]
• c_dependent = T / absent ; license = N[circular_dependency]

Blocks
• block(local) = T

Adequacy
• aa1 = B[method_conflict]
• aa2 = T
• a_model:prediction = B[adequacy_conflict]
• aa_circular = N[circular_dependency]
```

**Diagnostics**
- warning: method_conflict (aa1)
- error: circular_dependency (aa_circular)

### A13 — Core JudgedExpr

**Track:** Core semantics  
**Focus:** judged_expr, criterion_binding, missing_criterion

**Canonical source**
```limnalis
bundle A13_core_judged_expr {
  frame {
    system Test;
    namespace Judgment;
    scale service;
    task review;
    regime nominal;
  }

  evaluator ev0 {
    kind institution;
    binding test://eval/auth_truth_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  local {
    c1: safe(grid_state) judged_by test://eval/judged_inner_v1;
    c2: valid(token_A) judged_by test://missing_criterion;
  }
}
```

**AST / normalization expectations**
- c1, c2 -> JudgedExprNode wrapping PredicateExprNode

**Evaluation expectations**
```text
Claims
• c1 = T / absent
• c2 = N[missing_binding] / absent

Blocks
• block(local) = N
```

**Diagnostics**
- error: missing_binding (c2)

### A14 — Adjudicated resolution

**Track:** Core semantics  
**Focus:** adjudicated, governance_stack, claim_and_block_adjudication

**Canonical source**
```limnalis
bundle A14_adjudicated_resolution {
  frame {
    system Test;
    namespace Governance;
    scale service;
    task review;
    regime nominal;
  }

  evaluator ev_primary {
    kind model;
    role primary;
    binding test://eval/atoms_v1;
  }

  evaluator ev_adversarial {
    kind model;
    role adversarial;
    binding test://eval/adversarial_v1;
  }

  resolution_policy rp_adj {
    kind adjudicated;
    members [ev_primary, ev_adversarial];
    binding test://resolution/adjudicated_v1;
  }

  local {
    c1: p;
    c2: (b AND n);
  }
}
```

**AST / normalization expectations**
- ResolutionPolicyNode(kind=adjudicated, binding=test://resolution/adjudicated_v1)
- Claim and block aggregation both route through adjudication binding

**Evaluation expectations**
```text
Claims
• c1 = B[evaluator_conflict] / conflicted
• c2 = F / absent

Blocks
• block(local) = F
```

**Diagnostics:** none required.

### B1 — Grid contingency bundle

**Track:** Domain  
**Focus:** grid, causal, emergence, baseline, transport

**Canonical source**
```limnalis
bundle B1_grid_contingency {
  frame {
    system PowerGrid;
    namespace ACLoadFlow;
    scale micro;
    task operations;
    regime contingency;
    version v2;
  }

  evaluator ev_grid {
    kind model;
    binding test://eval/grid_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev_grid];
  }

  baseline margin {
    kind point;
    criterion ref test://baseline/reactive_margin_zero;
    frame @{system=PowerGrid, namespace=ACLoadFlow, scale=micro, task=operations, regime=contingency};
    evaluation_mode on_reference;
  }

  evidence scada_bus7 {
    kind measurement;
    binding test://data/scada_bus7;
    completeness 0.93;
    internal_conflict 0.02;
  }

  evidence pmu_bus7 {
    kind measurement;
    binding test://data/pmu_bus7;
    completeness 0.96;
    internal_conflict 0.01;
  }

  evidence_relation er_bus7 {
    lhs scada_bus7;
    rhs pmu_bus7;
    kind conflicts;
    score 0.72;
    refs [test://audit/bus7_disagreement];
  }

  anchor a_nminus1 {
    term symbol Nminus1;
    subtype idealization;
    status active;

    adequacy {
      id aa_n1_pred;
      task prediction;
      producer ev_grid;
      score 0.98;
      threshold 0.95;
      method sim://checks/n1_pred;
    }

    adequacy {
      id aa_n1_ctrl;
      task control;
      producer ev_grid;
      score 0.91;
      threshold 0.90;
      method sim://checks/n1_ctrl;
    }

    adequacy {
      id aa_n1_expl;
      task explanation;
      producer ev_grid;
      score 0.63;
      threshold 0.75;
      method audit://postmortem/n1_expl;
    }
  }

  bridge b_micro_to_regional {
    from @{system=PowerGrid, namespace=ACLoadFlow, scale=micro, task=operations, regime=contingency};
    to @{system=PowerGrid, namespace=PlanningModel, scale=regional, task=planning, regime=n-1};
    via test://bridge/pattern_only;
    preserve [power_balance];
    lose [phase_angle, switching_order];
    risk [aggregation_reversal];
    transport {
      mode metadata_only;
    }
  }

  local {
    c1: overload(line_B);
    c2: overload(line_B) =>[obs] voltage_drop(bus_7) refs [scada_bus7, pmu_bus7];
  }

  systemic {
    c3: voltage_instability EMRG when reactive_margin --> |0:margin| while demand_ramp_gt(0.02_pu_per_min) until load_shed(zone_2) uses [a_nminus1] refs [scada_bus7] annotations {"license_task": "control"};
  }

  meta {
    c4: declare Nminus1 as idealization within @{system=PowerGrid, namespace=ACLoadFlow, regime=contingency};
    c5: note "N-1 is acceptable for dispatch prediction but weak as a restoration explanation model.";
  }
}
```

**AST / normalization expectations**
- c2 -> CausalExprNode(mode=obs)
- c3 -> EmergenceExprNode
- c5 -> NoteExprNode
- a_nminus1 adequacy entries -> AdequacyAssessmentNode with producer

**Evaluation expectations**
```text
Claims
• c1 = T / absent
• c2 = B[source_conflict] / conflicted
• c3 = T / partial ; license = T
• c4 = T / inapplicable

Blocks
• block(local) = B
• block(systemic) = T
• block(meta) = T

Transports
• q1: metadata_only

Adequacy
• a_nminus1:prediction = T
• a_nminus1:control = T
• a_nminus1:explanation = F[threshold_not_met]
```

**Diagnostics:** none required.

### B2 — JWT access / adequacy bundle

**Track:** Domain  
**Focus:** jwt, judged_expr, institutional_evaluator, fiction_layer

**Canonical source**
```limnalis
bundle B2_jwt_access {
  frame {
    system Auth;
    namespace JWTGateway;
    scale service;
    task access_decision;
    regime steady_state;
    version v1;
  }

  evaluator ev_gateway {
    kind institution;
    binding test://eval/jwt_gateway_v1;
    evidence_policy test://policy/jwt_support_v1;
  }

  resolution_policy rp0 {
    kind single;
    members [ev_gateway];
  }

  evidence e_sig {
    kind measurement;
    binding test://auth/siglog_tok_A;
    completeness 1.0;
  }

  evidence e_clock {
    kind measurement;
    binding test://auth/clock_tok_A;
    completeness 1.0;
  }

  evidence e_rev {
    kind dataset;
    binding test://auth/revocation_cache_tok_A;
    completeness 0.70;
    internal_conflict 0.10;
  }

  anchor a_stateless {
    term symbol stateless_session;
    subtype idealization;
    status active;

    adequacy {
      id aa_stateless_access;
      task access_decision;
      producer ev_gateway;
      score 0.96;
      threshold 0.90;
      method test://method/stateless_access;
    }

    adequacy {
      id aa_stateless_revocation;
      task revocation;
      producer ev_gateway;
      score 0.41;
      threshold 0.90;
      method test://method/stateless_revocation;
    }
  }

  anchor a_clock {
    term symbol bounded_clock_skew;
    subtype idealization;
    status active;

    adequacy {
      id aa_clock_access;
      task access_decision;
      producer ev_gateway;
      score 0.93;
      threshold 0.90;
      method test://method/clock_access;
    }
  }

  joint_adequacy ja_access {
    anchors [a_stateless, a_clock];
    assessment {
      id ja_access_assess;
      task access_decision;
      producer ev_gateway;
      score 0.92;
      threshold 0.90;
      method test://method/jwt_joint_access;
    }
  }

  local {
    c1: sig_valid(tok_A) refs [e_sig];
    c2: token_not_expired(tok_A) refs [e_clock] uses [a_clock] annotations {"license_task": "access_decision"};
    c3: access_allowed(tok_A) judged_by test://policy/auth_access_v3 uses [a_stateless, a_clock] refs [e_sig, e_clock, e_rev] annotations {"license_task": "access_decision"};
    c4: revocation_immediate(tok_A) refs [e_rev] uses [a_stateless] annotations {"license_task": "revocation"};
  }

  meta {
    c5: declare stateless_session as idealization within @{system=Auth, namespace=JWTGateway, task=access_decision};
  }
}
```

**AST / normalization expectations**
- c3 -> JudgedExprNode
- adequacy entries -> AdequacyAssessmentNode with explicit producer

**Evaluation expectations**
```text
Claims
• c1 = T / supported
• c2 = T / supported ; license = T
• c3 = T / partial ; license = T
• c4 = T / partial ; license = F[threshold_not_met]
• c5 = T / inapplicable

Blocks
• block(local) = T
• block(meta) = T
```

**Diagnostics:** none required.

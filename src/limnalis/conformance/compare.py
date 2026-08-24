"""Compare actual evaluation results to fixture expectations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..runtime.runner import BundleResult, SessionResult, StepResult
from .fixtures import FixtureCase
from .runner import CaseRunResult


# ---------------------------------------------------------------------------
# Comparison result types
# ---------------------------------------------------------------------------


@dataclass
class FieldMismatch:
    """A single field-level mismatch between expected and actual."""

    path: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return f"  {self.path}: expected={self.expected!r}, actual={self.actual!r}"


@dataclass
class CaseComparison:
    """Comparison result for a single fixture case."""

    case_id: str
    passed: bool
    mismatches: list[FieldMismatch] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    # Warning-level report entries that never affect `passed`. Expectations
    # are partial matchers (spec §18.2), so an under-specified pin is not a
    # failure — but some partial pins are worth surfacing to corpus authors,
    # e.g. a B/N truth pinned without a reason while the actual result
    # carries one (§8.5 makes B/N reasons mandatory on the RESULT side, so
    # the actual is spec-correct and only the pin is incomplete).
    warnings: list[FieldMismatch] = field(default_factory=list)

    def summary(self) -> str:
        if self.skipped:
            return f"{self.case_id}: SKIP ({self.skip_reason})"
        if self.error:
            return f"{self.case_id}: ERROR ({self.error})"
        if self.passed:
            return f"{self.case_id}: PASS"
        return f"{self.case_id}: FAIL ({len(self.mismatches)} mismatches)"

    def details(self) -> str:
        lines = [self.summary()]
        for m in self.mismatches:
            lines.append(str(m))
        for w in self.warnings:
            lines.append(f"  [warning]{str(w)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _compare_eval_snapshot(
    path: str,
    expected: dict[str, Any],
    actual_node: Any,
    mismatches: list[FieldMismatch],
    warnings: list[FieldMismatch] | None = None,
) -> None:
    """Compare an expected EvalSnapshot dict to an actual EvalNode/EvalSnapshot.

    Expectations are partial matchers (spec §18.2): only pinned keys are
    compared. One partial pin is additionally surfaced as a WARNING (never a
    mismatch): a pinned B/N truth with no pinned reason while the actual
    result carries one. §8.5 makes B/N reasons mandatory on the result side,
    so the actual value is spec-correct — failing it would punish compliant
    output — but the pin is under-specified and worth flagging to the corpus
    author (m7 red-team MEDIUM follow-up on the reason pins being
    load-bearing).
    """
    if actual_node is None:
        mismatches.append(FieldMismatch(path, expected, None))
        return

    # actual_node could be an EvalNode (Pydantic model) or dict
    if hasattr(actual_node, "model_dump"):
        actual = actual_node.model_dump(exclude_none=True)
    elif isinstance(actual_node, dict):
        actual = actual_node
    else:
        mismatches.append(FieldMismatch(path, expected, str(actual_node)))
        return

    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if act_val != exp_val:
            mismatches.append(FieldMismatch(f"{path}.{key}", exp_val, act_val))

    if (
        warnings is not None
        and expected.get("truth") in ("B", "N")
        and "reason" not in expected
        and actual.get("reason") is not None
    ):
        warnings.append(
            FieldMismatch(
                f"{path}.reason",
                "(B/N truth pinned without reason)",
                actual.get("reason"),
            )
        )


def _compare_claim(
    path: str,
    claim_exp: dict[str, Any],
    step_result: StepResult,
    claim_id: str,
    mismatches: list[FieldMismatch],
    warnings: list[FieldMismatch] | None = None,
) -> None:
    """Compare expected claim results to actual."""
    # per_evaluator comparison
    per_ev_exp = claim_exp.get("per_evaluator")
    if per_ev_exp is not None:
        actual_per_ev = step_result.per_claim_per_evaluator.get(claim_id, {})
        for ev_id, ev_exp in per_ev_exp.items():
            actual_ev = actual_per_ev.get(ev_id)
            if isinstance(ev_exp, dict):
                _compare_eval_snapshot(
                    f"{path}.per_evaluator.{ev_id}",
                    ev_exp,
                    actual_ev,
                    mismatches,
                    warnings,
                )
            elif isinstance(ev_exp, str):
                # Simple truth value comparison
                actual_truth = actual_ev.truth if actual_ev else None
                if actual_truth != ev_exp:
                    mismatches.append(
                        FieldMismatch(
                            f"{path}.per_evaluator.{ev_id}.truth",
                            ev_exp,
                            actual_truth,
                        )
                    )

        # Reverse check: flag extra evaluators in actual but not expected
        extra_evs = set(actual_per_ev.keys()) - set(per_ev_exp.keys())
        for ev_id in sorted(extra_evs):
            mismatches.append(
                FieldMismatch(f"{path}.per_evaluator.{ev_id}", "not expected", actual_per_ev[ev_id])
            )

    # aggregate comparison
    agg_exp = claim_exp.get("aggregate")
    if agg_exp is not None:
        actual_agg = step_result.per_claim_aggregates.get(claim_id)
        if isinstance(agg_exp, dict):
            _compare_eval_snapshot(
                f"{path}.aggregate",
                agg_exp,
                actual_agg,
                mismatches,
                warnings,
            )
        elif isinstance(agg_exp, str):
            actual_truth = actual_agg.truth if actual_agg else None
            if actual_truth != agg_exp:
                mismatches.append(
                    FieldMismatch(f"{path}.aggregate.truth", agg_exp, actual_truth)
                )

    # license comparison
    license_exp = claim_exp.get("license")
    if license_exp is not None:
        actual_license = step_result.per_claim_licenses.get(claim_id)
        _compare_license(
            f"{path}.license", license_exp, actual_license, mismatches, warnings
        )


def _compare_license(
    path: str,
    license_exp: dict[str, Any],
    actual_license: Any,
    mismatches: list[FieldMismatch],
    warnings: list[FieldMismatch] | None = None,
) -> None:
    """Compare expected license results to actual."""
    if actual_license is None:
        mismatches.append(FieldMismatch(path, license_exp, None))
        return

    overall_exp = license_exp.get("overall")
    if overall_exp is not None:
        actual_overall = actual_license.overall if hasattr(actual_license, "overall") else None
        if actual_overall is not None:
            if hasattr(actual_overall, "model_dump"):
                actual_dict = actual_overall.model_dump(exclude_none=True)
            else:
                actual_dict = actual_overall
            for key, exp_val in overall_exp.items():
                act_val = actual_dict.get(key)
                if act_val != exp_val:
                    mismatches.append(
                        FieldMismatch(f"{path}.overall.{key}", exp_val, act_val)
                    )
        else:
            mismatches.append(FieldMismatch(f"{path}.overall", overall_exp, None))

    # individual anchor expectations
    individual_exp = license_exp.get("individual")
    if individual_exp is not None and isinstance(individual_exp, dict):
        individual_actual = {}
        if hasattr(actual_license, "individual"):
            for entry in actual_license.individual:
                key = f"{entry.anchor_id}:{entry.task}" if hasattr(entry, "task") else entry.anchor_id
                individual_actual[key] = entry
        for key, exp_val in individual_exp.items():
            if key not in individual_actual:
                mismatches.append(FieldMismatch(f"{path}.individual.{key}", exp_val, None))
            else:
                act = individual_actual[key]
                act_dict = act.model_dump(exclude_none=True) if hasattr(act, "model_dump") else act
                for fld, fld_val in exp_val.items():
                    if act_dict.get(fld) != fld_val:
                        mismatches.append(
                            FieldMismatch(
                                f"{path}.individual.{key}.{fld}",
                                fld_val,
                                act_dict.get(fld),
                            )
                        )

    # joint expectations
    joint_exp = license_exp.get("joint")
    if joint_exp is not None:
        actual_joint = list(getattr(actual_license, "joint", []) or [])
        if isinstance(joint_exp, dict):
            _compare_eval_snapshot(
                f"{path}.joint",
                joint_exp,
                actual_joint[0] if actual_joint else None,
                mismatches,
                warnings,
            )
            if len(actual_joint) > 1:
                mismatches.append(
                    FieldMismatch(
                        f"{path}.joint.length",
                        1,
                        len(actual_joint),
                    )
                )
        elif isinstance(joint_exp, list):
            expected_by_id: dict[str, dict[str, Any]] = {}
            unnamed_expected: list[dict[str, Any]] = []
            for idx, exp_entry in enumerate(joint_exp):
                if not isinstance(exp_entry, dict):
                    mismatches.append(
                        FieldMismatch(f"{path}.joint[{idx}]", "dict", exp_entry)
                    )
                    continue
                joint_id = exp_entry.get("joint_id")
                if isinstance(joint_id, str):
                    expected_by_id[joint_id] = exp_entry
                else:
                    unnamed_expected.append(exp_entry)

            actual_by_id: dict[str, Any] = {
                entry.joint_id: entry
                for entry in actual_joint
                if hasattr(entry, "joint_id")
            }

            for joint_id, exp_entry in expected_by_id.items():
                _compare_eval_snapshot(
                    f"{path}.joint[{joint_id}]",
                    exp_entry,
                    actual_by_id.get(joint_id),
                    mismatches,
                    warnings,
                )

            if unnamed_expected:
                sorted_actual = sorted(
                    actual_joint,
                    key=lambda entry: getattr(entry, "joint_id", ""),
                )
                for idx, exp_entry in enumerate(unnamed_expected):
                    _compare_eval_snapshot(
                        f"{path}.joint[{idx}]",
                        exp_entry,
                        sorted_actual[idx] if idx < len(sorted_actual) else None,
                        mismatches,
                        warnings,
                    )

            if len(actual_joint) != len(joint_exp):
                mismatches.append(
                    FieldMismatch(
                        f"{path}.joint.length",
                        len(joint_exp),
                        len(actual_joint),
                    )
                )


def _compare_block(
    path: str,
    block_exp: dict[str, Any],
    step_result: StepResult,
    block_id: str,
    mismatches: list[FieldMismatch],
    warnings: list[FieldMismatch] | None = None,
) -> None:
    """Compare expected block results to actual."""
    # Find actual block result by matching block stratum name or id
    actual_block_per_ev = step_result.per_block_per_evaluator
    actual_block_agg = step_result.per_block_aggregates

    # Look up actual block by id. If block_id is a stratum name (local/systemic/meta),
    # try to find the matching block.
    resolved_block_id = _resolve_block_id(block_id, step_result)

    # per_evaluator comparison
    per_ev_exp = block_exp.get("per_evaluator")
    if per_ev_exp is not None:
        actual_per_ev = actual_block_per_ev.get(resolved_block_id, {})
        for ev_id, ev_exp in per_ev_exp.items():
            actual_ev = actual_per_ev.get(ev_id)
            if isinstance(ev_exp, str):
                # Simple truth value
                actual_truth = actual_ev.truth if actual_ev else None
                if actual_truth != ev_exp:
                    mismatches.append(
                        FieldMismatch(
                            f"{path}.per_evaluator.{ev_id}.truth",
                            ev_exp,
                            actual_truth,
                        )
                    )
            elif isinstance(ev_exp, dict):
                _compare_eval_snapshot(
                    f"{path}.per_evaluator.{ev_id}",
                    ev_exp,
                    actual_ev,
                    mismatches,
                    warnings,
                )

        # Reverse check: flag extra evaluators in actual but not expected
        extra_evs = set(actual_per_ev.keys()) - set(per_ev_exp.keys())
        for ev_id in sorted(extra_evs):
            mismatches.append(
                FieldMismatch(f"{path}.per_evaluator.{ev_id}", "not expected", actual_per_ev[ev_id])
            )

    # aggregate comparison
    agg_exp = block_exp.get("aggregate")
    if agg_exp is not None:
        actual_agg = actual_block_agg.get(resolved_block_id)
        if isinstance(agg_exp, str):
            actual_truth = actual_agg.truth if actual_agg else None
            if actual_truth != agg_exp:
                mismatches.append(
                    FieldMismatch(f"{path}.aggregate.truth", agg_exp, actual_truth)
                )
        elif isinstance(agg_exp, dict):
            _compare_eval_snapshot(
                f"{path}.aggregate", agg_exp, actual_agg, mismatches, warnings
            )

    # claimIds comparison (m7 red-team MEDIUM-2): when the expectation pins
    # the block's claim listing, compare it ORDER-SENSITIVELY against
    # BlockResult.claims. The corpus convention pins claimIds as the
    # declaration-ordered array of ALL claims in the block (evaluable or
    # not) — the vendored ast_decision canonical BlockResult shape declares
    # `claimIds: [string]` as an ordered list, and D6's whole point is that
    # claim_subset changes this listing.
    claim_ids_exp = block_exp.get("claimIds")
    if claim_ids_exp is not None:
        block_result = None
        for br in getattr(step_result, "block_results", None) or []:
            if br.block_id == resolved_block_id:
                block_result = br
                break
        actual_claim_ids = (
            list(block_result.claims) if block_result is not None else None
        )
        if actual_claim_ids != list(claim_ids_exp):
            mismatches.append(
                FieldMismatch(
                    f"{path}.claimIds", list(claim_ids_exp), actual_claim_ids
                )
            )


def _resolve_block_id(block_name: str, step_result: StepResult) -> str:
    """Resolve a block name (like 'local', 'systemic', 'meta') to an actual block id.

    Fixture expectations may use stratum names as block identifiers.
    Block results use the actual block id from the AST (e.g. 'local#1').
    """
    # First try direct match
    if block_name in step_result.per_block_aggregates:
        return block_name

    # Try matching by looking at block results for stratum-named blocks
    for br in step_result.block_results:
        if br.block_id == block_name:
            return br.block_id
        # The block_id often IS the stratum name in fixture bundles
        if br.block_id.lower() == block_name.lower():
            return br.block_id
        # Match stratum prefix: e.g. "local#1" matches "local"
        if br.block_id.split("#")[0].lower() == block_name.lower():
            return br.block_id

    # Return as-is if no match found
    return block_name


def _compare_transport(
    path: str,
    transport_exp: dict[str, Any],
    actual_transport: Any,
    mismatches: list[FieldMismatch],
    warnings: list[FieldMismatch] | None = None,
) -> None:
    """Compare expected transport results to actual."""
    if actual_transport is None:
        mismatches.append(FieldMismatch(path, transport_exp, None))
        return

    # status comparison
    status_exp = transport_exp.get("status")
    if status_exp is not None:
        actual_status = actual_transport.status if hasattr(actual_transport, "status") else None
        if actual_status != status_exp:
            mismatches.append(
                FieldMismatch(f"{path}.status", status_exp, actual_status)
            )

    # sourceAggregate comparison
    src_agg_exp = transport_exp.get("sourceAggregate")
    if src_agg_exp is not None:
        actual_src = actual_transport.srcAggregate if hasattr(actual_transport, "srcAggregate") else None
        _compare_eval_snapshot(
            f"{path}.sourceAggregate", src_agg_exp, actual_src, mismatches, warnings
        )

    # dstAggregate comparison
    dst_agg_exp = transport_exp.get("dstAggregate")
    if dst_agg_exp is not None:
        actual_dst = actual_transport.dstAggregate if hasattr(actual_transport, "dstAggregate") else None
        _compare_eval_snapshot(
            f"{path}.dstAggregate", dst_agg_exp, actual_dst, mismatches, warnings
        )

    # per_evaluator comparison
    per_ev_exp = transport_exp.get("per_evaluator")
    if per_ev_exp is not None:
        actual_per_ev = actual_transport.per_evaluator if hasattr(actual_transport, "per_evaluator") else {}
        for ev_id, ev_exp in per_ev_exp.items():
            actual_ev = actual_per_ev.get(ev_id)
            _compare_eval_snapshot(
                f"{path}.per_evaluator.{ev_id}",
                ev_exp,
                actual_ev,
                mismatches,
                warnings,
            )
        extra_evs = set(actual_per_ev.keys()) - set(per_ev_exp.keys())
        for ev_id in sorted(extra_evs):
            mismatches.append(
                FieldMismatch(f"{path}.per_evaluator.{ev_id}", "not expected", actual_per_ev[ev_id])
            )


def _compare_diagnostics(
    path: str,
    expected_diags: list[dict[str, Any]],
    actual_diags: list[dict[str, Any]],
    mismatches: list[FieldMismatch],
) -> list[dict[str, Any]]:
    """Compare expected diagnostics to actual.

    Matching is done by (code, severity) pair. Subject is compared
    only when specified in expected.

    Returns the list of actual diagnostics that were not matched by any
    expected entry (i.e. unmatched extras).
    """
    remaining_actuals = list(actual_diags)  # mutable copy to consume matches

    for i, exp_diag in enumerate(expected_diags):
        exp_code = exp_diag.get("code")
        exp_severity = exp_diag.get("severity")
        exp_subject = exp_diag.get("subject")

        # Find matching actual diagnostic (consume on match to prevent reuse)
        matched = False
        for j, act_diag in enumerate(remaining_actuals):
            code_match = act_diag.get("code") == exp_code
            sev_match = act_diag.get("severity") == exp_severity
            if exp_subject is not None:
                subj_match = act_diag.get("subject", act_diag.get("claim_id", act_diag.get("block_id"))) == exp_subject
            else:
                subj_match = True

            if code_match and sev_match and subj_match:
                matched = True
                remaining_actuals.pop(j)
                break

        if not matched:
            mismatches.append(
                FieldMismatch(
                    f"{path}[{i}]",
                    exp_diag,
                    "not found in actual diagnostics",
                )
            )

    # Return remaining unmatched actuals so the caller can decide whether
    # to treat them as failures (e.g. when expected was explicitly empty).
    return remaining_actuals


# ---------------------------------------------------------------------------
# Main comparison entry point
# ---------------------------------------------------------------------------


def compare_case(case: FixtureCase, run_result: CaseRunResult) -> CaseComparison:
    """Compare a case's expected results against actual run results."""
    if run_result.error is not None:
        return CaseComparison(
            case_id=case.id, passed=False, error=run_result.error
        )

    if run_result.bundle_result is None:
        return CaseComparison(
            case_id=case.id,
            passed=False,
            error="No bundle result produced",
        )

    mismatches: list[FieldMismatch] = []
    warnings: list[FieldMismatch] = []
    bundle_result = run_result.bundle_result
    expected = case.expected

    # Bundle bridge ids feed the transport reverse check's scaffolding
    # exemption; None (bundle unavailable, e.g. stubbed run results) skips
    # that reverse check.
    bundle = getattr(run_result, "bundle", None)
    bridge_ids: set[str] | None = None
    if bundle is not None:
        bridge_ids = {
            bridge_id
            for bridge_id in (
                getattr(bridge, "id", None)
                for bridge in (getattr(bundle, "bridges", None) or [])
            )
            if isinstance(bridge_id, str)
        }

    # Compare sessions
    expected_sessions = expected.get("sessions", [])

    # If expected has no sessions (e.g. A2), we just check diagnostics
    if expected_sessions:
        actual_session_count = len(bundle_result.session_results)
        expected_session_count = len(expected_sessions)
        if actual_session_count != expected_session_count:
            mismatches.append(
                FieldMismatch(
                    "sessions.length",
                    expected_session_count,
                    actual_session_count,
                )
            )

        compare_count = min(expected_session_count, actual_session_count)
        for si in range(compare_count):
            sess_exp = expected_sessions[si]
            sess_result = bundle_result.session_results[si]
            _compare_session(
                f"sessions[{si}]", sess_exp, sess_result, mismatches,
                warnings, bridge_ids,
            )

    # Compare top-level diagnostics
    # Collect all diagnostics from bundle + sessions + steps
    all_actual_diags = _collect_all_diagnostics(bundle_result)
    expected_diags = expected.get("diagnostics")
    if expected_diags is not None:
        unmatched_diags = _compare_diagnostics(
            "diagnostics", expected_diags, all_actual_diags, mismatches
        )
        if unmatched_diags:
            actual_diag_indices = {
                id(diag): idx for idx, diag in enumerate(all_actual_diags)
            }
            for extra in unmatched_diags:
                if extra.get("severity") in {"error", "fatal"}:
                    actual_idx = actual_diag_indices.get(id(extra), -1)
                    mismatches.append(
                        FieldMismatch(
                            f"diagnostics[{actual_idx}]",
                            "not expected",
                            extra,
                        )
                    )

    # Compare baseline_states if specified
    baseline_states_exp = expected.get("baseline_states")
    if baseline_states_exp is not None:
        _compare_baseline_states(
            "baseline_states", baseline_states_exp, bundle_result, mismatches
        )

    # Compare adequacy_expectations if specified
    adequacy_exp = expected.get("adequacy_expectations")
    if adequacy_exp is not None:
        _compare_adequacy(
            "adequacy_expectations", adequacy_exp, bundle_result, mismatches
        )

    return CaseComparison(
        case_id=case.id,
        passed=len(mismatches) == 0,
        mismatches=mismatches,
        warnings=warnings,
    )


def _compare_session(
    path: str,
    sess_exp: dict[str, Any],
    sess_result: SessionResult,
    mismatches: list[FieldMismatch],
    warnings: list[FieldMismatch] | None = None,
    bridge_ids: set[str] | None = None,
) -> None:
    """Compare a single session's expected results to actual.

    Both directions are checked (m7 red-team MEDIUM-2). Forward: every
    pinned claim/block/transport is compared. Reverse: when a step
    expectation pins a claims/blocks/transports map at all, actual entries
    absent from that map are flagged as mismatches, mirroring the
    extra-diagnostic convention (only meaningful extras fail) with two
    documented exemptions:

    - non-evaluable (note) claims: the vendored corpus convention omits
      note claims from expected claims (they still surface in the eval maps
      with reason=non_evaluable_note — e.g. vendored B1 c5), so they are the
      "benign severity" analog and are tolerated;
    - bridge-id transport entries: the runtime records per-bridge
      scaffolding TransportResults alongside query results (e.g. vendored
      A7 b_pattern/b_exec) which expectations pin by QUERY id only, so
      actual entries keyed by a declared bundle bridge id are tolerated.
      ``bridge_ids=None`` means the bundle is unavailable and the transport
      reverse check is skipped (the exemption cannot be computed).

    A step expectation with no claims/blocks/transports key pins nothing at
    that level and triggers no reverse check (§18.2 partial matchers).
    """
    steps_exp = sess_exp.get("steps", [])
    actual_step_count = len(sess_result.step_results)
    expected_step_count = len(steps_exp)
    if actual_step_count != expected_step_count:
        mismatches.append(
            FieldMismatch(
                f"{path}.steps.length",
                expected_step_count,
                actual_step_count,
            )
        )

    for si in range(min(expected_step_count, actual_step_count)):
        step_exp = steps_exp[si]
        step_result = sess_result.step_results[si]
        step_path = f"{path}.steps[{si}]"

        # Compare claims
        claims_exp = step_exp.get("claims", {})
        for claim_id, claim_exp in claims_exp.items():
            _compare_claim(
                f"{step_path}.claims.{claim_id}",
                claim_exp,
                step_result,
                claim_id,
                mismatches,
                warnings,
            )

        # Reverse check: actual evaluated claims absent from a pinned claims
        # map are mismatches (verifies §16.2.1 claim_subset absence — an
        # excluded claim leaking back into results must fail the case).
        if "claims" in step_exp:
            actual_claim_ids = set(
                getattr(step_result, "per_claim_per_evaluator", None) or {}
            ) | set(getattr(step_result, "per_claim_aggregates", None) or {})
            classifications = (
                getattr(step_result, "per_claim_classifications", None) or {}
            )
            for claim_id in sorted(actual_claim_ids - set(claims_exp)):
                classification = classifications.get(claim_id)
                if (
                    classification is not None
                    and getattr(classification, "evaluable", True) is False
                ):
                    continue  # note-claim exemption (see docstring)
                actual_entry = (
                    (getattr(step_result, "per_claim_aggregates", None) or {}).get(claim_id)
                    or (getattr(step_result, "per_claim_per_evaluator", None) or {}).get(claim_id)
                )
                mismatches.append(
                    FieldMismatch(
                        f"{step_path}.claims.{claim_id}",
                        "not expected",
                        actual_entry,
                    )
                )

        # Compare blocks
        blocks_exp = step_exp.get("blocks", {})
        for block_id, block_exp in blocks_exp.items():
            _compare_block(
                f"{step_path}.blocks.{block_id}",
                block_exp,
                step_result,
                block_id,
                mismatches,
                warnings,
            )

        # Reverse check: actual blocks absent from a pinned blocks map.
        if "blocks" in step_exp:
            resolved_pinned_blocks = {
                _resolve_block_id(block_id, step_result) for block_id in blocks_exp
            }
            actual_block_ids = set(
                getattr(step_result, "per_block_aggregates", None) or {}
            ) | set(getattr(step_result, "per_block_per_evaluator", None) or {})
            for block_id in sorted(actual_block_ids - resolved_pinned_blocks):
                actual_entry = (
                    (getattr(step_result, "per_block_aggregates", None) or {}).get(block_id)
                    or (getattr(step_result, "per_block_per_evaluator", None) or {}).get(block_id)
                )
                mismatches.append(
                    FieldMismatch(
                        f"{step_path}.blocks.{block_id}",
                        "not expected",
                        actual_entry,
                    )
                )

        # Compare transports
        transports_exp = step_exp.get("transports", {})
        for transport_id, transport_exp in transports_exp.items():
            actual_transport = step_result.transport_results.get(transport_id)
            _compare_transport(
                f"{step_path}.transports.{transport_id}",
                transport_exp,
                actual_transport,
                mismatches,
                warnings,
            )

        # Reverse check: actual transport entries absent from a pinned
        # transports map, exempting per-bridge scaffolding entries.
        if "transports" in step_exp and bridge_ids is not None:
            actual_transport_ids = set(
                getattr(step_result, "transport_results", None) or {}
            )
            extras = actual_transport_ids - set(transports_exp) - bridge_ids
            for transport_id in sorted(extras):
                mismatches.append(
                    FieldMismatch(
                        f"{step_path}.transports.{transport_id}",
                        "not expected",
                        step_result.transport_results[transport_id],
                    )
                )


def _collect_all_diagnostics(bundle_result: BundleResult) -> list[dict[str, Any]]:
    """Collect all diagnostics from bundle, sessions, and steps."""
    all_diags: list[dict[str, Any]] = list(bundle_result.diagnostics)
    for sess in bundle_result.session_results:
        all_diags.extend(sess.diagnostics)
        for step in sess.step_results:
            all_diags.extend(step.diagnostics)
    return all_diags


def _compare_baseline_states(
    path: str,
    expected: dict[str, str],
    bundle_result: BundleResult,
    mismatches: list[FieldMismatch],
) -> None:
    """Compare expected baseline states to actual."""
    # Baseline states are in session results
    actual_baselines: dict[str, Any] = {}
    for sess in bundle_result.session_results:
        actual_baselines.update(sess.baseline_states)

    for bl_id, exp_status in expected.items():
        actual = actual_baselines.get(bl_id)
        if actual is None:
            mismatches.append(
                FieldMismatch(f"{path}.{bl_id}", exp_status, None)
            )
        else:
            actual_status = actual.get("status") if isinstance(actual, dict) else str(actual)
            if actual_status != exp_status:
                mismatches.append(
                    FieldMismatch(f"{path}.{bl_id}", exp_status, actual_status)
                )


def _flatten_adequacy_store(raw_store: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Flatten the nested adequacy store into a flat dict of {id: result_dict}.

    The store may be structured as:
        {"per_assessment": {id: {...}}, "per_anchor_task": {id: {...}}, "joint": {id: {...}}}
    or may already be flat. We merge all sub-dicts into one flat lookup.
    """
    flat: dict[str, dict[str, Any]] = {}

    def _store_entry(entry_id: str, entry_val: Any) -> None:
        if isinstance(entry_val, dict):
            flat[entry_id] = entry_val
        elif hasattr(entry_val, "model_dump"):
            flat[entry_id] = entry_val.model_dump(exclude_none=True)

    # Always preserve top-level adequacy entries (flat shape), while also
    # flattening any nested runtime sections that may coexist in mixed-shape runs.
    for k, v in raw_store.items():
        if k in {"per_assessment", "per_anchor_task", "joint"}:
            continue
        _store_entry(k, v)

    for sub_key in ("per_assessment", "per_anchor_task", "joint"):
        sub = raw_store.get(sub_key, {})
        if isinstance(sub, dict):
            for entry_id, entry_val in sub.items():
                _store_entry(entry_id, entry_val)

    return flat




def _merge_adequacy_store(acc: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge adequacy stores without clobbering prior sessions.

    Supports both nested runtime shape and already-flat map shape.
    """
    has_nested_sections = any(
        key in incoming for key in ("per_assessment", "per_anchor_task", "joint")
    )

    if has_nested_sections:
        for k, v in incoming.items():
            if k not in {"per_assessment", "per_anchor_task", "joint"}:
                acc[k] = v

        for sub_key in ("per_assessment", "per_anchor_task", "joint"):
            sub = incoming.get(sub_key)
            if isinstance(sub, dict):
                target = acc.setdefault(sub_key, {})
                if isinstance(target, dict):
                    target.update(sub)
    else:
        # Preserve already-flat stores by merging top-level entries directly.
        acc.update(incoming)

    return acc

def _compare_adequacy(
    path: str,
    expected: dict[str, dict[str, Any]],
    bundle_result: BundleResult,
    mismatches: list[FieldMismatch],
) -> None:
    """Compare expected adequacy results to actual."""
    # Adequacy results are in session results' adequacy_store
    raw_adequacy: dict[str, Any] = {}
    for sess in bundle_result.session_results:
        _merge_adequacy_store(raw_adequacy, sess.adequacy_store)

    # Flatten nested structure for comparison
    actual_adequacy = _flatten_adequacy_store(raw_adequacy)

    for adeq_id, exp_vals in expected.items():
        actual = actual_adequacy.get(adeq_id)
        if actual is None:
            mismatches.append(
                FieldMismatch(f"{path}.{adeq_id}", exp_vals, None)
            )
        else:
            actual_dict = actual if isinstance(actual, dict) else (
                actual.model_dump(exclude_none=True)
                if hasattr(actual, "model_dump")
                else {"value": actual}
            )
            for key, exp_val in exp_vals.items():
                act_val = actual_dict.get(key)
                if act_val != exp_val:
                    mismatches.append(
                        FieldMismatch(
                            f"{path}.{adeq_id}.{key}",
                            exp_val,
                            act_val,
                        )
                    )

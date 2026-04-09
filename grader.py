"""
IncidentOpsEnv  Rule-Based Grader
===================================
Computes a structured score from the InternalState at the end of an episode.

Score breakdown (total = 1.0):
  evidence_score       0.15   viewed the right signals
  severity_score       0.15   classified severity correctly
  cause_score          0.20   correct root-cause hypothesis
  mitigation_score     0.25   applied the right fix on the right target
  communication_score  0.10   posted a status update (+ escalated if required)
  efficiency_score     0.10   resolved without wasting the step budget
  safety_score         0.05   no harmful mitigations applied (starts full, penalised)

All sub-scores are in [0, 1].  Final weighted sum is in [0, 1].
Negative terminal penalty  applied when the episode ends without resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from models import InternalState, RewardComponents, ScoreComponents

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Score weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS: dict[str, float] = {
    "evidence":      0.15,
    "severity":      0.15,
    "cause":         0.20,
    "mitigation":    0.25,
    "communication": 0.10,
    "efficiency":    0.10,
    "safety":        0.05,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


@dataclass
class GradeResult:
    total: float                  # weighted sum in [0, 1]
    components: ScoreComponents   # per-dimension scores
    reward_components: RewardComponents  # mapped for Reward model
    summary: str                  # human-readable verdict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def grade_episode(state: InternalState, task_module) -> GradeResult:
    """
    Score a completed (or timed-out) episode.

    Args:
        state:       The final InternalState from the environment.
        task_module: The task module (task_easy / task_medium / task_hard)
                     that exposes RELEVANT_LOG_SERVICES and HARMFUL_MITIGATIONS.
    """
    sc = _score_evidence(state, task_module)
    ss = _score_severity(state)
    cs = _score_cause(state)
    ms = _score_mitigation(state)
    coms = _score_communication(state)
    es = _score_efficiency(state)
    saf = _score_safety(state)

    components = ScoreComponents(
        evidence_score=sc,
        severity_score=ss,
        cause_score=cs,
        mitigation_score=ms,
        communication_score=coms,
        efficiency_score=es,
        safety_score=saf,
    )

    total = (
        sc   * WEIGHTS["evidence"]
        + ss   * WEIGHTS["severity"]
        + cs   * WEIGHTS["cause"]
        + ms   * WEIGHTS["mitigation"]
        + coms * WEIGHTS["communication"]
        + es   * WEIGHTS["efficiency"]
        + saf  * WEIGHTS["safety"]
    )

    # Penalise episodes that were never resolved (did not call RESOLVE_INCIDENT)
    if not state.resolved:
        total = max(0.0, total - 0.15)

    reward_components = RewardComponents(
        evidence_collection=sc,
        severity_correctness=ss,
        root_cause_correctness=cs,
        mitigation_correctness=ms,
        communication_quality=coms,
        efficiency=es,
        safety=saf,
    )

    summary = _build_summary(state, components, total)
    # Force score into strictly (0, 1) range per hackathon validation rules
    # (prevents exact 0.0 or 1.0)
    total = max(0.01, min(0.99, total))

    return GradeResult(
        total=round(total, 4),
        components=components,
        reward_components=reward_components,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------

def _score_evidence(state: InternalState, task_module) -> float:
    """Partial credit for each relevant log service viewed."""
    em = state.evidence_map
    relevant: set[str] = getattr(task_module, "RELEVANT_LOG_SERVICES", set())

    points = 0.0
    max_points = 0.0

    # Alerts (mandatory baseline)
    max_points += 1.0
    if em.alerts_viewed:
        points += 1.0

    # Relevant logs
    for svc in relevant:
        max_points += 1.0
        if em.logs_viewed.get(svc):
            points += 1.0

    # Bonus for checking metrics on at least one relevant service
    max_points += 0.5
    if any(em.metrics_checked.get(svc) for svc in relevant):
        points += 0.5

    # Deploys checked (always useful)
    max_points += 0.5
    if em.deploys_checked:
        points += 0.5

    return min(1.0, points / max_points) if max_points else 0.0


def _score_severity(state: InternalState) -> float:
    return 1.0 if state.severity_classified_correctly else 0.0


def _score_cause(state: InternalState) -> float:
    return 1.0 if state.hypothesis_correct else 0.0


def _score_mitigation(state: InternalState) -> float:
    """Full credit for correct fix; half credit if fix applied but on wrong target."""
    if state.mitigation_correct:
        return 1.0
    if state.mitigation_applied is not None:
        # Applied something but it was wrong  partial credit for attempting
        return 0.2
    return 0.0


def _score_communication(state: InternalState) -> float:
    """
    Full credit = posted status update + escalated when required.
    Half credit if only one of the two required steps was done.
    """
    score = 0.0
    steps = 0
    required = 0

    # Status update is always required
    required += 1
    if state.communication_posted:
        score += 1.0
        steps += 1

    if state.requires_escalation:
        required += 1
        if state.escalation_correct:
            score += 1.0
            steps += 1

    return score / required if required else 1.0


def _score_efficiency(state: InternalState) -> float:
    """
    Reward finishing earlier. Steps used = episode_step.
    Full credit if resolved in  60 % of budget.
    Scales down linearly to 0 at 100 % of budget.
    Timeout (not resolved) gets 0.
    """
    if not state.resolved:
        return 0.0

    used_ratio = state.episode_step / state.max_steps
    if used_ratio <= 0.60:
        return 1.0
    if used_ratio >= 1.0:
        return 0.0
    return round(1.0 - (used_ratio - 0.60) / 0.40, 4)


def _score_safety(state: InternalState) -> float:
    """
    Starts at 1.0, penalised if harmful mitigations were applied.
    Each harmful action costs 0.5 (floor 0).
    """
    sc = state.score_components.safety_score
    return max(0.0, sc)


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(state: InternalState, sc: ScoreComponents, total: float) -> str:
    lines = [
        f"=== Episode Grade: {total:.2%} ===",
        f"  Incident   : {state.incident_id} ({state.task_name})",
        f"  Resolved   : {'YES' if state.resolved else 'NO  timed out or never resolved'}",
        f"  Steps used : {state.episode_step}/{state.max_steps}",
        "",
        "  Score breakdown:",
        f"    Evidence collection  : {sc.evidence_score:.2f}  (weight {WEIGHTS['evidence']:.0%})",
        f"    Severity correctness : {sc.severity_score:.2f}  (weight {WEIGHTS['severity']:.0%})",
        f"    Root-cause accuracy  : {sc.cause_score:.2f}  (weight {WEIGHTS['cause']:.0%})",
        f"    Mitigation quality   : {sc.mitigation_score:.2f}  (weight {WEIGHTS['mitigation']:.0%})",
        f"    Communication        : {sc.communication_score:.2f}  (weight {WEIGHTS['communication']:.0%})",
        f"    Efficiency           : {sc.efficiency_score:.2f}  (weight {WEIGHTS['efficiency']:.0%})",
        f"    Safety               : {sc.safety_score:.2f}  (weight {WEIGHTS['safety']:.0%})",
    ]

    # Verdict
    if total >= 0.85:
        verdict = "EXCELLENT  optimal or near-optimal response"
    elif total >= 0.65:
        verdict = "GOOD  correct resolution with minor gaps"
    elif total >= 0.45:
        verdict = "PARTIAL  some correct steps but key errors"
    else:
        verdict = "POOR  significant errors or failed to resolve"
    lines += ["", f"  Verdict: {verdict}"]

    # Warnings
    if state.harmful_mitigation_applied:
        lines.append("    WARNING: A harmful mitigation was applied  safety penalty incurred")
    if state.premature_resolved:
        lines.append("    WARNING: RESOLVE_INCIDENT called before mitigation  premature resolution")
    if state.spam_counter > 2:
        lines.append(f"    WARNING: Spam detected  {state.spam_counter} repeated identical actions")

    return "\n".join(lines)

"""
IncidentOpsEnv  Main Environment
===================================
A deterministic, step-based simulation environment for incident response.

Usage:
    from env import IncidentOpsEnv
    from models import Action, ActionType, ServiceName

    env = IncidentOpsEnv(task="easy")
    obs = env.reset()

    action = Action(action_type=ActionType.VIEW_ALERTS)
    result = env.step(action)          # StepResult
    print(result.observation)
    print(result.reward)

Tasks:  "easy" | "medium" | "hard"
"""

from __future__ import annotations

import importlib
import types
from typing import Optional

from models import (
    Action, ActionType, EvidenceMap, FeatureFlagName,
    InternalState, MessageTemplate, Observation, Reward,
    RewardComponents, ScoreComponents, ServiceName, StepResult,
    SeverityLevel, TeamName,
)
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State
from grader import grade_episode

# ---------------------------------------------------------------------------
# Per-step reward constants
# ---------------------------------------------------------------------------
R_NEW_EVIDENCE        =  0.05   # viewing a new evidence source
R_REDUNDANT_ACTION    = -0.02   # repeated action (spam penalty)
R_CORRECT_SEVERITY    =  0.10
R_WRONG_SEVERITY      = -0.05
R_CORRECT_CAUSE       =  0.10
R_WRONG_CAUSE         = -0.05
R_CORRECT_MITIGATION  =  0.20
R_HARMFUL_MITIGATION  = -0.20
R_WRONG_MITIGATION    = -0.05
R_COMMUNICATION       =  0.05
R_CORRECT_ESCALATION  =  0.05
R_WRONG_ESCALATION    = -0.02
R_CORRECT_RESOLVE     =  0.20
R_PREMATURE_RESOLVE   = -0.15
R_TIMEOUT             = -0.10

SPAM_THRESHOLD = 3   # same action repeated this many times = spam


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class IncidentOpsEnv(Environment):
    """
    Deterministic, single-episode incident response simulation environment.

    After calling reset(), step() must be called with an Action.
    The episode ends when:
      - RESOLVE_INCIDENT action is submitted, OR
      - The step budget is exhausted (done=True, timeout penalty applied).
    """

    SUPPORTS_CONCURRENT_SESSIONS = True
    VALID_TASKS = ("easy", "medium", "hard")

    def __init__(self, task_id: Optional[str] = None, **kwargs) -> None:
        """
        Initialize the environment. 
        Note: The server may pass task_id here or via reset().
        """
        self._task_name = task_id or "easy"
        if self._task_name not in self.VALID_TASKS:
            # Default to easy if invalid task received
            self._task_name = "easy"
            
        self._task_module: Optional[types.ModuleType] = None
        self._obs: Optional[Observation] = None
        self._state: Optional[InternalState] = None

    @classmethod
    def get_task_ids(cls) -> list[str]:
        return list(cls.VALID_TASKS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reset(self, task_id: Optional[str] = None, **kwargs) -> Observation:
        """Load task data and return the initial observation."""
        if task_id and task_id in self.VALID_TASKS:
            self._task_name = task_id
            
        module_name = f"tasks.task_{self._task_name}"
        self._task_module = importlib.import_module(module_name)

        factory_fn = getattr(self._task_module, f"get_{self._task_name}_task")
        self._obs, self._state = factory_fn()
        return self._obs

    def get_metadata(self) -> dict:
        """Return environment and task metadata for the benchmark suite."""
        return {
            "name": "incident-ops-env",
            "version": "1.0.0",
            "description": "Production SRE Incident Simulator",
            "task_ids": self.get_task_ids(),
            "action_space": [e.value for e in ActionType],
            "observation_space": {
                "incident_id": "str",
                "affected_services": "list[str]",
                "remaining_step_budget": "int"
            },
            "grading_enabled": True
        }

    def close(self) -> None:
        """Cleanup resources."""
        self._state = None
        self._task_module = None
        self._obs = None

    @property
    def state(self) -> State:
        """Return the current state payload handling standard episode tracking."""
        if self._state is None:
            return State(episode_id="0", step_count=0)
        return State(episode_id="1", step_count=self._state.episode_step)

    def step(self, action: Action) -> Observation:  # type: ignore[override]
        """
        Process an action and return observation (which contains reward and done).

        Raises:
            RuntimeError: if reset() has not been called first.
        """
        if self._state is None or self._obs is None:
            raise RuntimeError("Call reset() before step().")

        if self._state.resolved or self._state.episode_step >= self._state.max_steps:
            raise RuntimeError("Episode is already done. Call reset() to start a new episode.")

        self._state.episode_step += 1

        # Spam tracking
        action_key = self._action_key(action)
        self._state.repeated_actions[action_key] = (
            self._state.repeated_actions.get(action_key, 0) + 1
        )
        is_spam = self._state.repeated_actions[action_key] >= SPAM_THRESHOLD

        # Dispatch
        scalar, result_text = self._dispatch(action, is_spam)

        if is_spam:
            self._state.spam_counter += 1
            scalar += R_REDUNDANT_ACTION

        # Accumulate penalty
        if scalar < 0:
            self._state.penalties_accumulated += abs(scalar)

        self._state.cumulative_reward += scalar

        # Update observation
        self._obs.action_history.append(action_key)
        self._obs.last_action_result = result_text
        self._obs.remaining_step_budget = (
            self._state.max_steps - self._state.episode_step
        )
        self._obs.is_resolved = self._state.resolved

        # Check for natural timeout (budget exhausted without resolving)
        done = self._state.resolved
        timeout = (
            not done
            and self._state.episode_step >= self._state.max_steps
        )
        if timeout:
            scalar += R_TIMEOUT
            self._state.cumulative_reward += R_TIMEOUT
            done = True
            result_text += "\n Step budget exhausted  episode terminated."

        # Build reward
        grade = grade_episode(self._state, self._task_module) if done else None
        reward = Reward(
            scalar=round(scalar, 4),
            total_cumulative_score=round(self._state.cumulative_reward, 4),
            rationale=result_text,
            components=grade.reward_components if grade else None,
        )

        info: dict = {}
        if done:
            info["grade"] = "Graded"
            info["summary"] = grade.summary if grade else ""
            info["final_score"] = grade.total if grade else 0.0

        obs_ret = self._obs.model_copy()
        obs_ret.reward = float(reward.scalar)
        obs_ret.done = done
        if done and grade:
            obs_ret.final_score = float(grade.total)
        return obs_ret

    @property
    def task_module(self) -> Optional[types.ModuleType]:
        return self._task_module

    @property
    def internal_state(self) -> Optional[InternalState]:
        """Exposed for testing/debugging  not available to agent during episode."""
        return self._state

    # ------------------------------------------------------------------
    # Action dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, action: Action, is_spam: bool) -> tuple[float, str]:
        t = action.action_type

        if t == ActionType.VIEW_ALERTS:
            return self._do_view_alerts()
        elif t == ActionType.VIEW_LOGS:
            return self._do_view_logs(action)
        elif t == ActionType.CHECK_METRICS:
            return self._do_check_metrics(action)
        elif t == ActionType.CHECK_RECENT_DEPLOYS:
            return self._do_check_deploys()
        elif t == ActionType.VIEW_DEPENDENCY_MAP:
            return self._do_view_dependency_map()
        elif t == ActionType.INSPECT_FEATURE_FLAGS:
            return self._do_inspect_flags()
        elif t == ActionType.CLASSIFY_SEVERITY:
            return self._do_classify_severity(action)
        elif t == ActionType.HYPOTHESIZE_ROOT_CAUSE:
            return self._do_hypothesize(action)
        elif t == ActionType.RESTART_SERVICE:
            return self._do_restart_service(action)
        elif t == ActionType.ROLLBACK_DEPLOY:
            return self._do_rollback_deploy(action)
        elif t == ActionType.SCALE_SERVICE:
            return self._do_scale_service(action)
        elif t == ActionType.DISABLE_FEATURE_FLAG:
            return self._do_disable_flag(action)
        elif t == ActionType.POST_STATUS_UPDATE:
            return self._do_post_status_update(action)
        elif t == ActionType.ESCALATE_TEAM:
            return self._do_escalate_team(action)
        elif t == ActionType.RESOLVE_INCIDENT:
            return self._do_resolve()
        else:
            return 0.0, f"Unknown action type: {t}"

    # ------------------------------------------------------------------
    # Individual action implementations
    # ------------------------------------------------------------------

    def _do_view_alerts(self) -> tuple[float, str]:
        em = self._state.evidence_map
        alerts = self._task_module.get_alerts()
        self._obs.known_alerts = alerts
        if em.alerts_viewed:
            return 0.0, "Alerts already retrieved. No new information."
        em.alerts_viewed = True
        lines = [f"  [{a.alert_id}] {a.service} | {a.severity.upper()} | {a.message}" for a in alerts]
        return R_NEW_EVIDENCE, "Alerts retrieved:\n" + "\n".join(lines)

    def _do_view_logs(self, action: Action) -> tuple[float, str]:
        if not action.target_service:
            return 0.0, "view_logs requires a target_service."
        svc = action.target_service if isinstance(action.target_service, str) else action.target_service.value
        em = self._state.evidence_map
        logs = self._task_module.get_logs(svc)
        if not logs:
            return 0.0, f"No logs available for service '{svc}'."
        self._obs.retrieved_logs[svc] = logs
        if em.logs_viewed.get(svc):
            return 0.0, f"Logs for '{svc}' already retrieved."
        em.logs_viewed[svc] = True
        lines = [f"  [{e.timestamp}] {e.level}  {e.message}" for e in logs]
        return R_NEW_EVIDENCE, f"Logs for {svc}:\n" + "\n".join(lines)

    def _do_check_metrics(self, action: Action) -> tuple[float, str]:
        if not action.target_service:
            return 0.0, "check_metrics requires a target_service."
        svc = action.target_service if isinstance(action.target_service, str) else action.target_service.value
        em = self._state.evidence_map
        metric = self._task_module.get_metrics(svc)
        if metric is None:
            return 0.0, f"No metrics data available for '{svc}'."
        self._obs.retrieved_metrics[svc] = metric
        if em.metrics_checked.get(svc):
            return 0.0, f"Metrics for '{svc}' already checked."
        em.metrics_checked[svc] = True
        return R_NEW_EVIDENCE, (
            f"Metrics for {svc}:\n"
            f"  Error rate : {metric.error_rate_pct:.1f}%\n"
            f"  Latency p99: {metric.latency_p99_ms:.0f} ms\n"
            f"  RPS        : {metric.requests_per_sec:.0f}\n"
            f"  CPU        : {metric.cpu_usage_pct:.1f}%\n"
            f"  Memory     : {metric.memory_usage_pct:.1f}%"
        )

    def _do_check_deploys(self) -> tuple[float, str]:
        em = self._state.evidence_map
        deploys = self._task_module.get_deploys()
        self._obs.recent_deploys = deploys
        if em.deploys_checked:
            return 0.0, "Recent deploys already retrieved."
        em.deploys_checked = True
        lines = [
            f"  [{d.deploy_id}] {d.service} {d.version} @ {d.deployed_at} by {d.deployed_by}  {d.status}"
            + (f"\n    Notes: {d.notes}" if d.notes else "")
            for d in deploys
        ]
        return R_NEW_EVIDENCE, "Recent deploys:\n" + "\n".join(lines)

    def _do_view_dependency_map(self) -> tuple[float, str]:
        em = self._state.evidence_map
        dep_map = self._task_module.get_dependency_map()
        self._obs.dependency_map = dep_map
        if em.dependency_viewed:
            return 0.0, "Dependency map already retrieved."
        em.dependency_viewed = True
        lines = [f"  {svc}  [{', '.join(deps) if deps else 'none'}]" for svc, deps in dep_map.items()]
        return R_NEW_EVIDENCE, "Dependency map:\n" + "\n".join(lines)

    def _do_inspect_flags(self) -> tuple[float, str]:
        em = self._state.evidence_map
        flags = self._task_module.get_feature_flags()
        self._obs.feature_flag_states = flags
        if em.flags_inspected:
            return 0.0, "Feature flags already inspected."
        em.flags_inspected = True
        lines = [
            f"  {f.flag_name}: {'ENABLED' if f.enabled else 'disabled'} "
            f"({f.rollout_pct}%)  last modified {f.last_modified}"
            for f in flags
        ]
        return R_NEW_EVIDENCE, "Feature flags:\n" + "\n".join(lines)

    def _do_classify_severity(self, action: Action) -> tuple[float, str]:
        if not action.severity:
            return 0.0, "classify_severity requires a severity level."
        sev = action.severity if isinstance(action.severity, str) else action.severity.value
        self._state.severity_classified = sev
        self._obs.classified_severity = sev
        correct_sev = self._state.correct_severity
        correct_val = correct_sev if isinstance(correct_sev, str) else correct_sev.value
        if sev == correct_val:
            self._state.severity_classified_correctly = True
            self._state.score_components.severity_score = 1.0
            return R_CORRECT_SEVERITY, f"Severity classified as {sev.upper()}   matches ground truth."
        else:
            return R_WRONG_SEVERITY, f"Severity classified as {sev.upper()}   does not match incident severity."

    def _do_hypothesize(self, action: Action) -> tuple[float, str]:
        if not action.hypothesis:
            return 0.0, "hypothesize_root_cause requires a hypothesis."
        hyp = action.hypothesis if isinstance(action.hypothesis, str) else action.hypothesis.value
        self._state.hypothesis_submitted = hyp
        correct_rc = self._state.root_cause
        correct_val = correct_rc if isinstance(correct_rc, str) else correct_rc.value
        if hyp == correct_val:
            self._state.hypothesis_correct = True
            self._state.score_components.cause_score = 1.0
            return R_CORRECT_CAUSE, f"Root cause hypothesis '{hyp}'   matches ground truth."
        else:
            return R_WRONG_CAUSE, f"Root cause hypothesis '{hyp}'   incorrect."

    def _do_restart_service(self, action: Action) -> tuple[float, str]:
        if not action.target_service:
            return 0.0, "restart_service requires a target_service."
        svc = action.target_service if isinstance(action.target_service, str) else action.target_service.value
        return self._apply_mitigation("restart_service", svc, action)

    def _do_rollback_deploy(self, action: Action) -> tuple[float, str]:
        if not action.target_service:
            return 0.0, "rollback_deploy requires a target_service."
        svc = action.target_service if isinstance(action.target_service, str) else action.target_service.value
        return self._apply_mitigation("rollback_deploy", svc, action)

    def _do_scale_service(self, action: Action) -> tuple[float, str]:
        if not action.target_service:
            return 0.0, "scale_service requires a target_service."
        svc = action.target_service if isinstance(action.target_service, str) else action.target_service.value
        return self._apply_mitigation("scale_service", svc, action)

    def _do_disable_flag(self, action: Action) -> tuple[float, str]:
        if not action.target_flag:
            return 0.0, "disable_feature_flag requires a target_flag."
        flag = action.target_flag if isinstance(action.target_flag, str) else action.target_flag.value
        return self._apply_mitigation("disable_feature_flag", flag, action)

    def _apply_mitigation(self, action_type_str: str, target: str, action: Action) -> tuple[float, str]:
        from models import ActionType as AT
        state = self._state

        # Check for harmful mitigation
        harmful_set = getattr(self._task_module, "HARMFUL_MITIGATIONS", set())
        # Build ActionType from string
        try:
            at_enum = AT(action_type_str)
        except ValueError:
            at_enum = None

        # Normalize harmful check to handle both strings and enums in the set
        is_harmful = False
        for h_type, h_target in harmful_set:
            h_target_val = h_target.value if hasattr(h_target, 'value') else h_target
            if at_enum == h_type and target == h_target_val:
                is_harmful = True
                break

        if is_harmful:
            state.harmful_mitigation_applied = True
            state.score_components.safety_score = max(
                0.0, state.score_components.safety_score - 0.5
            )
            state.mitigation_applied = f"{action_type_str}({target})"
            return R_HARMFUL_MITIGATION, (
                f"  Harmful mitigation applied: {action_type_str}({target}). "
                "This action is incorrect and potentially disruptive."
            )

        # Check correctness
        correct_mit = state.correct_mitigation
        correct_mit_val = correct_mit if isinstance(correct_mit, str) else correct_mit.value
        correct_target = state.correct_mitigation_target
        if isinstance(correct_target, (ServiceName, FeatureFlagName)):
            correct_target = correct_target.value

        if action_type_str == correct_mit_val and target == correct_target:
            state.mitigation_applied = f"{action_type_str}({target})"
            state.mitigation_correct = True
            state.score_components.mitigation_score = 1.0
            return R_CORRECT_MITIGATION, (
                f" Correct mitigation applied: {action_type_str}({target}). "
                "Service is recovering."
            )
        else:
            state.mitigation_applied = f"{action_type_str}({target})"
            return R_WRONG_MITIGATION, (
                f" Mitigation {action_type_str}({target}) applied but is incorrect for this incident."
            )

    def _do_post_status_update(self, action: Action) -> tuple[float, str]:
        template = action.message_template
        if template is None:
            return 0.0, "post_status_update requires a message_template."
        msg = template if isinstance(template, str) else template.value
        self._obs.posted_status_updates.append(msg)
        if not self._state.communication_posted:
            self._state.communication_posted = True
            self._state.score_components.communication_score = (
                self._state.score_components.communication_score + 0.5
            )
            return R_COMMUNICATION, f"Status update posted: \"{msg}\""
        return 0.0, "Status update already posted  no additional credit."

    def _do_escalate_team(self, action: Action) -> tuple[float, str]:
        if not action.team_name:
            return 0.0, "escalate_team requires a team_name."
        team = action.team_name if isinstance(action.team_name, str) else action.team_name.value
        self._obs.escalated_teams.append(team)
        self._state.escalation_done = True

        if not self._state.requires_escalation:
            return R_WRONG_ESCALATION, f"Escalated to {team}  but this incident did not require escalation."

        correct_team = self._state.required_escalation_team
        correct_val = correct_team if isinstance(correct_team, str) else (correct_team.value if correct_team else None)
        if team == correct_val:
            self._state.escalation_correct = True
            self._state.score_components.communication_score = (
                self._state.score_components.communication_score + 0.5
            )
            return R_CORRECT_ESCALATION, f" Escalated to {team}  correct team notified."
        else:
            return R_WRONG_ESCALATION, f" Escalated to {team}  wrong team for this incident."

    def _do_resolve(self) -> tuple[float, str]:
        state = self._state
        # Premature resolution: mitigation not yet applied
        if not state.mitigation_applied:
            state.premature_resolved = True
            state.resolved = True
            return R_PREMATURE_RESOLVE, (
                "  RESOLVE_INCIDENT called before any mitigation was applied. "
                "Incident closed prematurely."
            )
        state.resolved = True
        return R_CORRECT_RESOLVE, "Incident resolved. Episode complete."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _action_key(action: Action) -> str:
        parts = [action.action_type if isinstance(action.action_type, str) else action.action_type.value]
        for attr in ("target_service", "target_flag", "target_queue", "severity",
                     "hypothesis", "message_template", "team_name"):
            val = getattr(action, attr, None)
            if val is not None:
                parts.append(str(val.value) if hasattr(val, "value") else str(val))
        return "|".join(parts)


if __name__ == "__main__":
    # Standard OpenEnv entry point check
    print("Environment Loaded Successfully.")
    e = IncidentOpsEnv(task_id="easy")
    o = e.reset()
    print(f"Test reset complete: {o.incident_id}")

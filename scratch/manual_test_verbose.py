"""
Manual test: runs all 3 tasks (easy/medium/hard) through their optimal action sequences
and prints the full grader summary for each.
"""
import sys
sys.path.insert(0, ".")

from core_env import IncidentOpsEnv
from models import (
    Action, ActionType, ServiceName, RootCauseHypothesis,
    FeatureFlagName, TeamName, SeverityLevel, MessageTemplate,
)

# ---- EASY ----------------------------------------------------------------
print("=" * 60)
print("TASK: EASY  (DB connection pool exhaustion)")
print("=" * 60)
env = IncidentOpsEnv(task_id="easy")
obs = env.reset()
print(f"Incident ID  : {obs.incident_id}")
print(f"Summary      : {obs.incident_summary[:80]}...")
print(f"Step Budget  : {obs.remaining_step_budget}")
print()

actions_easy = [
    Action(action_type=ActionType.VIEW_ALERTS),
    Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.CLASSIFY_SEVERITY, severity=SeverityLevel.HIGH),
    Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.DB_CONNECTION_POOL_EXHAUSTION),
    Action(action_type=ActionType.POST_STATUS_UPDATE, message_template=MessageTemplate.INVESTIGATING),
    Action(action_type=ActionType.RESTART_SERVICE, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.RESOLVE_INCIDENT),
]
for a in actions_easy:
    result = env.step(a)
    snippet = result.last_action_result[:80].replace("\n", " ")
    print(f"  [{a.action_type:30}]  reward={result.reward:+.4f}  {snippet}")
    if result.done:
        print()
        print(result.last_action_result)
        print(f"\n>>> EASY FINAL SCORE : {result.final_score}")

# ---- MEDIUM --------------------------------------------------------------
print()
print("=" * 60)
print("TASK: MEDIUM  (bad deploy regression - checkout-service)")
print("=" * 60)
env2 = IncidentOpsEnv(task_id="medium")
obs2 = env2.reset()
print(f"Incident ID  : {obs2.incident_id}")
print(f"Summary      : {obs2.incident_summary[:80]}...")
print(f"Step Budget  : {obs2.remaining_step_budget}")
print()

actions_medium = [
    Action(action_type=ActionType.VIEW_ALERTS),
    Action(action_type=ActionType.CHECK_RECENT_DEPLOYS),
    Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.CHECKOUT_SERVICE),
    Action(action_type=ActionType.CLASSIFY_SEVERITY, severity=SeverityLevel.HIGH),
    Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.BAD_DEPLOY_REGRESSION),
    Action(action_type=ActionType.POST_STATUS_UPDATE, message_template=MessageTemplate.INVESTIGATING),
    Action(action_type=ActionType.ROLLBACK_DEPLOY, target_service=ServiceName.CHECKOUT_SERVICE),
    Action(action_type=ActionType.RESOLVE_INCIDENT),
]
for a in actions_medium:
    result = env2.step(a)
    snippet = result.last_action_result[:80].replace("\n", " ")
    print(f"  [{a.action_type:30}]  reward={result.reward:+.4f}  {snippet}")
    if result.done:
        print()
        print(result.last_action_result)
        print(f"\n>>> MEDIUM FINAL SCORE : {result.final_score}")

# ---- HARD ----------------------------------------------------------------
print()
print("=" * 60)
print("TASK: HARD  (auth-v2 feature flag misconfiguration)")
print("=" * 60)
env3 = IncidentOpsEnv(task_id="hard")
obs3 = env3.reset()
print(f"Incident ID  : {obs3.incident_id}")
print(f"Summary      : {obs3.incident_summary[:80]}...")
print(f"Step Budget  : {obs3.remaining_step_budget}")
print()

actions_hard = [
    Action(action_type=ActionType.VIEW_ALERTS),
    Action(action_type=ActionType.INSPECT_FEATURE_FLAGS),
    Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.AUTH_SERVICE),
    Action(action_type=ActionType.CLASSIFY_SEVERITY, severity=SeverityLevel.CRITICAL),
    Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.FEATURE_FLAG_MISCONFIGURATION),
    Action(action_type=ActionType.POST_STATUS_UPDATE, message_template=MessageTemplate.INVESTIGATING),
    Action(action_type=ActionType.ESCALATE_TEAM, team_name=TeamName.SECURITY),
    Action(action_type=ActionType.DISABLE_FEATURE_FLAG, target_flag=FeatureFlagName.AUTH_V2),
    Action(action_type=ActionType.RESOLVE_INCIDENT),
]
for a in actions_hard:
    result = env3.step(a)
    snippet = result.last_action_result[:80].replace("\n", " ")
    print(f"  [{a.action_type:30}]  reward={result.reward:+.4f}  {snippet}")
    if result.done:
        print()
        print(result.last_action_result)
        print(f"\n>>> HARD FINAL SCORE : {result.final_score}")

print()
print("=" * 60)
print("ALL 3 TASKS WITH GRADERS -- MANUAL VERIFICATION COMPLETE")
print("=" * 60)

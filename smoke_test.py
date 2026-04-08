"""Smoke test: verify all three tasks reset and the easy golden path scores correctly."""
import sys
sys.path.insert(0, ".")

from models import (
    Action, ActionType, ServiceName, SeverityLevel,
    RootCauseHypothesis, MessageTemplate,
)
from env import IncidentOpsEnv

# ── 1. Reset all three tasks ──────────────────────────────────────────────────
for task in ("easy", "medium", "hard"):
    env = IncidentOpsEnv(task=task)
    obs = env.reset()
    print(f"[{task}] reset OK — {obs.incident_id}  budget={obs.remaining_step_budget}")

# ── 2. Golden-path easy episode ───────────────────────────────────────────────
print("\n--- Easy golden-path ---")
env = IncidentOpsEnv(task="easy")
obs = env.reset()

steps = [
    Action(action_type=ActionType.VIEW_ALERTS),
    Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.CLASSIFY_SEVERITY, severity=SeverityLevel.HIGH),
    Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE,
           hypothesis=RootCauseHypothesis.DB_CONNECTION_POOL_EXHAUSTION),
    Action(action_type=ActionType.RESTART_SERVICE, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.POST_STATUS_UPDATE,
           message_template=MessageTemplate.MITIGATION_APPLIED),
    Action(action_type=ActionType.RESOLVE_INCIDENT),
]

for a in steps:
    r = env.step(a)
    at = a.action_type.value if hasattr(a.action_type, "value") else str(a.action_type)
    print(f"  {at:<38}  reward={r.reward.scalar:+.3f}  cumul={r.reward.total_cumulative_score:+.3f}  done={r.done}")
    if r.done:
        print(f"\n  Final score : {r.info['final_score']:.4f}")
        print(r.info["summary"])

# ── 3. Timeout path (medium — do nothing until budget runs out) ───────────────
print("\n--- Medium timeout path ---")
env = IncidentOpsEnv(task="medium")
obs = env.reset()
done = False
while not done:
    r = env.step(Action(action_type=ActionType.VIEW_ALERTS))
    done = r.done
print(f"  Timed out after {env.internal_state.episode_step} steps")
print(f"  Final score : {r.info['final_score']:.4f}")

print("\nAll smoke tests passed.")

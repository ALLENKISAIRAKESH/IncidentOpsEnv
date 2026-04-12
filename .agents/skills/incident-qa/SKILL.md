# /incident-qa — End-to-End Episode Quality Assurance
# Role: QA Lead (runs all tasks, validates scores, checks edge cases)

You are the QA Lead for IncidentOpsEnv. You run all 3 tasks end-to-end
with scripted agent sequences and validate that scores match expectations.

---

## Step 0 — Setup

```bash
echo "=== Incident QA ==="
cd scalar-space  # or wherever the project root is
python -c "from core_env import IncidentOpsEnv; print('Import OK')"
```

---

## Step 1 — Quick Smoke Test

```bash
python scratch/test_evals.py
```

If this fails, stop and run /investigate before continuing.
All 3 tasks must pass the basic grader smoke test.

---

## Step 2 — Optimal Agent Test (Easy Task)

Run the OPTIMAL action sequence for the easy task and verify score:

```python
from core_env import IncidentOpsEnv
from models import Action, ActionType, RootCauseHypothesis, SeverityLevel, ServiceName, MessageTemplate

env = IncidentOpsEnv()
obs = env.reset(task_id="easy")
print(f"Task: {obs.task_name}, Budget: {obs.remaining_step_budget}")

# Optimal path: evidence -> classify -> hypothesize -> mitigate -> communicate -> resolve
actions = [
    Action(action_type=ActionType.VIEW_ALERTS),
    Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.CHECK_METRICS, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.CLASSIFY_SEVERITY, severity=SeverityLevel.HIGH),
    Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.DB_CONNECTION_POOL_EXHAUSTION),
    Action(action_type=ActionType.RESTART_SERVICE, target_service=ServiceName.PAYMENT_API),
    Action(action_type=ActionType.POST_STATUS_UPDATE, message_template=MessageTemplate.SERVICE_RESTORED),
    Action(action_type=ActionType.RESOLVE_INCIDENT),
]

cumulative = 0.0
for action in actions:
    obs = env.step(action)
    cumulative += obs.reward
    print(f"[{action.action_type.value}] reward={obs.reward:.3f} done={obs.done}")
    if obs.done:
        print(f"FINAL SCORE: {obs.final_score:.4f}")
        assert obs.final_score >= 0.80, f"Easy optimal score too low: {obs.final_score}"
        print("PASS: Easy optimal score >= 0.80")
        break
```

---

## Step 3 — Harmful Mitigation Test

Verify harmful actions incur the correct penalty:

```python
from core_env import IncidentOpsEnv
from models import Action, ActionType, ServiceName, FeatureFlagName

env = IncidentOpsEnv()
obs = env.reset(task_id="easy")

obs = env.step(Action(action_type=ActionType.VIEW_ALERTS))
obs = env.step(Action(action_type=ActionType.ROLLBACK_DEPLOY, target_service=ServiceName.PAYMENT_API))
print(f"Harmful mitigation reward: {obs.reward}")
assert obs.reward <= -0.20, f"Harmful mitigation should penalize -0.20, got {obs.reward}"
print("PASS: Harmful mitigation penalty correct")
```

---

## Step 4 — Spam Detection Test

Verify repeated actions incur spam penalty:

```python
from core_env import IncidentOpsEnv
from models import Action, ActionType

env = IncidentOpsEnv()
obs = env.reset(task_id="easy")

# SPAM_THRESHOLD is 3 in core_env.py
for i in range(5):
    obs = env.step(Action(action_type=ActionType.VIEW_ALERTS))
    print(f"VIEW_ALERTS x{i+1}: reward={obs.reward}")

# By iteration 3+, reward should be negative (spam penalty)
# First view: +0.05, second and after: 0.0 or -0.02
```

---

## Step 5 — Premature Resolve Test

```python
from core_env import IncidentOpsEnv
from models import Action, ActionType

env = IncidentOpsEnv()
obs = env.reset(task_id="easy")

obs = env.step(Action(action_type=ActionType.VIEW_ALERTS))
obs = env.step(Action(action_type=ActionType.RESOLVE_INCIDENT))  # No mitigation applied
print(f"Premature resolve reward: {obs.reward}")
assert obs.reward <= -0.15, f"Premature resolve penalty should be >= 0.15, got {obs.reward}"
print("PASS: Premature resolve penalty correct")
```

---

## Step 6 — Step Budget Exhaustion Test

```python
from core_env import IncidentOpsEnv
from models import Action, ActionType

env = IncidentOpsEnv()
obs = env.reset(task_id="easy")
max_steps = obs.remaining_step_budget

# Fill all steps with VIEW_ALERTS (will hit spam after 3)
for i in range(max_steps):
    obs = env.step(Action(action_type=ActionType.VIEW_ALERTS))
    if obs.done:
        print(f"Episode ended at step {i+1} (done=True)")
        assert "budget exhausted" in obs.last_action_result.lower() or obs.final_score is not None
        break

print("PASS: Step budget exhaustion handled correctly")
```

---

## Step 7 — All 3 Tasks Optimal Score Check

```bash
python -c "
from core_env import IncidentOpsEnv
from models import Action, ActionType, RootCauseHypothesis, SeverityLevel
from models import ServiceName, FeatureFlagName, MessageTemplate, TeamName

OPTIMAL_PATHS = {
    'easy': [
        Action(action_type=ActionType.VIEW_ALERTS),
        Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.PAYMENT_API),
        Action(action_type=ActionType.CLASSIFY_SEVERITY, severity=SeverityLevel.HIGH),
        Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.DB_CONNECTION_POOL_EXHAUSTION),
        Action(action_type=ActionType.RESTART_SERVICE, target_service=ServiceName.PAYMENT_API),
        Action(action_type=ActionType.POST_STATUS_UPDATE, message_template=MessageTemplate.SERVICE_RESTORED),
        Action(action_type=ActionType.RESOLVE_INCIDENT),
    ],
}

for task_id, path in OPTIMAL_PATHS.items():
    env = IncidentOpsEnv()
    env.reset(task_id=task_id)
    obs = None
    for action in path:
        obs = env.step(action)
        if obs.done:
            break
    score = obs.final_score if obs else 0.0
    status = 'PASS' if score >= 0.80 else 'FAIL'
    print(f'[{status}] {task_id}: {score:.4f}')
"
```

---

## Step 8 — Score Clamping Check

Verify all scores are strictly in (0.01, 0.99):

```python
from core_env import IncidentOpsEnv
from grader import grade_episode
from models import InternalState, ScoreComponents

# Test minimum score (do nothing)
env = IncidentOpsEnv()
env.reset(task_id="easy")
obs = env.step(__import__('models').Action(action_type=__import__('models').ActionType.RESOLVE_INCIDENT))
if obs.done:
    assert 0.01 <= obs.final_score <= 0.99, f"Score out of range: {obs.final_score}"
    print(f"Min score: {obs.final_score:.4f} -- in (0.01, 0.99): PASS")
```

---

## Step 9 — QA Report

```
=== Incident QA Report ===
Date: [timestamp]

TASK SMOKE TESTS:
  easy:   [PASS | FAIL]
  medium: [PASS | FAIL]
  hard:   [PASS | FAIL]

OPTIMAL SCORE TESTS:
  easy:   [score] -- [PASS>=0.80 | FAIL]
  medium: [score] -- [PASS>=0.80 | FAIL]
  hard:   [score] -- [PASS>=0.80 | FAIL]

EDGE CASE TESTS:
  Harmful mitigation penalty: [PASS | FAIL]
  Spam detection:             [PASS | FAIL]
  Premature resolve:          [PASS | FAIL]
  Budget exhaustion:          [PASS | FAIL]
  Score clamping (0.01-0.99): [PASS | FAIL]

OVERALL: [ALL PASS | X FAILURES]

ISSUES FOUND:
- [list any issues]

RECOMMENDATION:
[Ready to deploy | Fix before deploying]
```

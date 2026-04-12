# /investigate — Root Cause Investigation for IncidentOpsEnv
# Role: Debugger (systematic root-cause debugging for broken env/tasks/grader)

You are a systematic debugger for IncidentOpsEnv. Something is wrong.
Your job is to find the root cause WITHOUT guessing. No fixes until you've
diagnosed the problem.

---

## Step 0 — Scope the Problem

Ask:
1. What broke? (wrong score? crash? import error? wrong observation?)
2. Which task? (easy / medium / hard / all?)
3. What changed recently? (code change? new task? grader update?)
4. What is the ACTUAL vs EXPECTED behavior?

Do NOT start fixing until you can state: "X happens when Y, but I expected Z."

---

## Step 1 — Reproduce Minimally

```bash
# Try to reproduce the issue in isolation
python -c "
from core_env import IncidentOpsEnv
from models import Action, ActionType

env = IncidentOpsEnv()
obs = env.reset(task_id='easy')
print('reset OK:', obs.incident_id)
result = env.step(Action(action_type=ActionType.VIEW_ALERTS))
print('step OK:', result.reward, result.done)
"
```

If this crashes, read the full traceback carefully.

---

## Step 2 — Layer-by-Layer Diagnosis

Work from the outermost layer inward:

**Layer 1: Import check**
```bash
python -c "
import core_env; print('core_env OK')
import grader; print('grader OK')
import models; print('models OK')
from tasks import task_easy, task_medium, task_hard; print('tasks OK')
from server import app; print('server OK')
"
```

**Layer 2: Task data check**
```bash
python -c "
from tasks.task_easy import get_easy_task, get_alerts, get_logs, RELEVANT_LOG_SERVICES
obs, state = get_easy_task()
print('Task factory OK')
print('Alerts:', len(get_alerts()))
print('Logs (payment-api):', len(get_logs('payment-api')))  
print('Relevant services:', RELEVANT_LOG_SERVICES)
print('Root cause:', state.root_cause)
print('Correct mitigation:', state.correct_mitigation, '->', state.correct_mitigation_target)
"
```

**Layer 3: Grader check**
```bash
python -c "
from grader import grade_episode, WEIGHTS
print('Weights sum:', sum(WEIGHTS.values()))
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, 'WEIGHTS do not sum to 1.0!'
print('Weights OK')
"
```

**Layer 4: Episode check**
```bash
python -c "
from core_env import IncidentOpsEnv
from models import Action, ActionType, RootCauseHypothesis, SeverityLevel, ServiceName

env = IncidentOpsEnv()
obs = env.reset(task_id='easy')
state = env.internal_state
print('Step budget:', state.max_steps)
print('Root cause:', state.root_cause)
print('Correct mitigation:', state.correct_mitigation, '->', state.correct_mitigation_target)
print('Correct severity:', state.correct_severity)
"
```

---

## Step 3 — Narrow the Blast Radius

Once you know WHICH layer is broken, narrow to WHICH function:

```bash
# For wrong score issues: test each grader component individually
python -c "
from grader import _score_evidence, _score_severity, _score_cause, _score_mitigation
from grader import _score_communication, _score_efficiency, _score_safety
from tasks.task_easy import get_easy_task, RELEVANT_LOG_SERVICES
import tasks.task_easy as task_mod

obs, state = get_easy_task()

# Simulate optimal run
state.evidence_map.alerts_viewed = True
for svc in RELEVANT_LOG_SERVICES:
    state.evidence_map.logs_viewed[svc] = True
    state.evidence_map.metrics_checked[svc] = True
state.evidence_map.deploys_checked = True
state.severity_classified_correctly = True
state.hypothesis_correct = True
state.mitigation_correct = True
state.mitigation_applied = 'restart_service(payment-api)'
state.communication_posted = True
state.resolved = True
state.episode_step = 5  # used 5/7 steps

print('evidence:', _score_evidence(state, task_mod))
print('severity:', _score_severity(state))
print('cause:', _score_cause(state))
print('mitigation:', _score_mitigation(state))
print('communication:', _score_communication(state))
print('efficiency:', _score_efficiency(state))
print('safety:', _score_safety(state))
"
```

---

## Step 4 — Root Cause Statement

Before fixing ANYTHING, write:

```
ROOT CAUSE:
  File: [filename, line number]
  What: [exact description]
  Why: [why it causes the symptom]
  Evidence: [what I ran to confirm this]

FIX:
  [Specific change needed]
  [Why this fix is correct]
  [What to test after the fix]
```

Do NOT write code until this statement is agreed upon.

---

## Step 5 — Fix and Verify

After fixing:

```bash
python scratch/test_evals.py
```

If any test fails, go back to Step 2. Do NOT ship with failing tests.

---

## Investigation Heuristics

**"Wrong score" issues** -- start with grader.py and InternalState
**"Import error" issues** -- check ASCII compliance first (non-ASCII in .py files)
**"Wrong observation" issues** -- check task factory function return values
**"None reward" issues** -- check action type dispatch in _dispatch()
**"Done=True prematurely" issues** -- check episode step counting
**"Score > 0.99 or < 0.01" issues** -- check grade_episode() clamp logic
**"Concurrent session bug" issues** -- verify each session has its own InternalState

**Never say "pre-existing" without proof.** Run the test on an unmodified file first.

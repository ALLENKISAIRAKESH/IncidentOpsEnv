# /task-review — Incident Task Data Consistency Review
# Role: Task Designer (reviews task_*.py files for correctness)

You are a meticulous Task Designer reviewing an IncidentOpsEnv task file
for internal consistency, evidence quality, and grader compatibility.

---

## Step 0 — Identify Target Task

```bash
echo "=== Task Review ==="
ls tasks/task_*.py
```

Ask: which task file to review? (easy / medium / hard / or a new one)

Read the full task file before proceeding.

---

## Step 1 — Structure Check

Verify the task file has ALL required components:

```
[ ] INCIDENT_ID    -- unique string (e.g. "INC-001")
[ ] TASK_NAME      -- snake_case (e.g. "database_pool_exhaustion")
[ ] MAX_STEPS      -- integer (7-20 depending on difficulty)

[ ] ALERTS         -- list[AlertItem], at least 1 alert directly related to root cause
[ ] LOGS           -- dict[str, list[LogEntry]], key = service name
[ ] METRICS        -- dict[str, MetricSnapshot], key = service name
[ ] DEPLOYS        -- list[DeployRecord]
[ ] FEATURE_FLAGS  -- list[FeatureFlagState]
[ ] DEPENDENCY_MAP -- dict[str, list[str]]

[ ] RELEVANT_LOG_SERVICES  -- set of service name strings (for grader)
[ ] HARMFUL_MITIGATIONS    -- set of (ActionType, target) tuples

[ ] get_TASKNAME_task()    -- returns (Observation, InternalState)
[ ] _allowed_actions()     -- returns list of allowed action strings
[ ] get_alerts()           -- returns ALERTS
[ ] get_logs(service)      -- returns combined LOGS + NOISE_LOGS for service
[ ] get_metrics(service)   -- returns METRICS.get(service)
[ ] get_deploys()          -- returns DEPLOYS
[ ] get_feature_flags()    -- returns FEATURE_FLAGS
[ ] get_dependency_map()   -- returns DEPENDENCY_MAP
```

Flag any missing component as BLOCKER.

---

## Step 2 — Evidence Chain Validation

Trace the OPTIMAL evidence path and verify it leads to the correct conclusion:

**Alerts** -- Do the alerts clearly point to the affected service?
- At minimum: one alert on the PRIMARY affected service
- For hard tasks: alerts may be indirect (downstream symptoms)

**Logs** -- Do the relevant logs contain smoking-gun messages?
- RELEVANT_LOG_SERVICES must list ALL services whose logs provide direct evidence
- Log messages must be specific enough to support the root cause hypothesis
- Check: `get_logs(svc)` returns non-empty for each service in RELEVANT_LOG_SERVICES

**Metrics** -- Do metrics match the narrative?
- Error rate should be HIGH (>20%) for P1/P2 incidents
- Latency should be anomalous (>2x normal) for latency-class incidents
- CPU/memory should show strain when the root cause is resource exhaustion

**Deploys** -- Correct for the scenario:
- BAD DEPLOY scenario: deploy within last 2-4 hours, AFTER incident started
- DB POOL scenario: no suspicious deploy (correct mitigation is NOT a rollback)
- FEATURE FLAG scenario: flag enabled/modified recently with suspicious timing

**Feature Flags** -- Correct enablement state:
- For feature flag misconfiguration: ONE flag should be suspicious (100% rollout, recent change)
- For other scenarios: flags should be ACTIVE but not the root cause

**Dependency Map** -- Shows the blast radius:
- Root cause service is a DEPENDENCY of affected services
- Map must be consistent with ALERTS (affected service IS in dependency chain)

---

## Step 3 — InternalState Validation

Check the InternalState in `get_TASKNAME_task()`:

```python
[ ] root_cause       -- matches a RootCauseHypothesis enum value
[ ] correct_mitigation -- matches an ActionType enum value (e.g. ActionType.RESTART_SERVICE)
[ ] correct_mitigation_target -- matches ServiceName or FeatureFlagName
[ ] correct_severity -- matches a SeverityLevel enum value
[ ] requires_escalation -- bool, True only for hard tasks (usually)
[ ] requires_communication -- True (always required for full communication score)
[ ] score_components.safety_score -- 1.0 (starts full, penalized for harmful actions)
```

---

## Step 4 — HARMFUL_MITIGATIONS Validation

For each harmful mitigation in HARMFUL_MITIGATIONS:

1. Is it an (ActionType, target) tuple?
2. Is the target a ServiceName/FeatureFlagName enum value or string that matches what the env uses?
3. Is the mitigation genuinely wrong for this specific incident?
4. Would it be a plausible mistake for an untrained agent?

Run this check:
```python
from tasks.task_easy import HARMFUL_MITIGATIONS
from models import ActionType, ServiceName, FeatureFlagName
for action_type, target in HARMFUL_MITIGATIONS:
    assert isinstance(action_type, ActionType), f"Not ActionType: {action_type}"
    target_val = target.value if hasattr(target, 'value') else target
    print(f"  HARMFUL: {action_type.value}({target_val})")
```

---

## Step 5 — ASCII Check

```bash
python -c "
from pathlib import Path
import sys
task_files = list(Path('tasks').glob('task_*.py'))
errors = []
for f in task_files:
    try:
        f.read_text(encoding='ascii')
    except UnicodeDecodeError as e:
        errors.append(f'{f}: {e}')
if errors:
    print('NON-ASCII FOUND:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
else:
    print('ASCII check PASSED for all task files')
"
```

---

## Step 6 — Score Prediction

Predict what score the OPTIMAL agent should get on this task:
- evidence_score = 1.0 (views alerts + all relevant logs + metrics)
- severity_score = 1.0 (classifies correctly)
- cause_score = 1.0 (correct hypothesis)
- mitigation_score = 1.0 (correct action on correct target)
- communication_score = 1.0 (posts update + escalates if required)
- efficiency_score: depends on how many steps are needed vs MAX_STEPS

Expected optimal final score: should be >= 0.85 for all difficulty levels.

If optimal score < 0.85: task may be too strict. Check MAX_STEPS.
If optimal score = 0.99: too easy. Consider reducing MAX_STEPS or adding red herrings.

---

## Step 7 — Report

Write a task review report:

```
=== Task Review Report: tasks/task_TASKNAME.py ===

STATUS: [PASS | PASS WITH WARNINGS | FAIL]

BLOCKERS:
- [any missing required components or broken evidence chains]

WARNINGS:
- [non-blocking issues: confusing log messages, borderline step budget, etc.]

SCORE PREDICTION (optimal agent):
- Evidence:      1.0
- Severity:      1.0
- Root cause:    1.0
- Mitigation:    1.0
- Communication: [0.5 or 1.0]
- Efficiency:    [calculated]
- Safety:        1.0
- TOTAL:         [weighted sum]

HARMFUL MITIGATIONS: [VALID | ISSUES]
ASCII CHECK: [PASS | FAIL]

RECOMMENDATION:
[Ready to deploy | Fix these issues first | Redesign needed]
```

# /retro — Sprint Retrospective for IncidentOpsEnv
# Role: Team Lead (cross-project retrospective, shipping streaks, learnings)

You are the Team Lead running a post-sprint retrospective for IncidentOpsEnv.

---

## Step 0 — Gather Sprint Data

```bash
echo "=== IncidentOpsEnv Retro ==="
git log --oneline --since="7 days ago" 2>/dev/null || git log --oneline -20
echo "---"
git diff --stat HEAD~10..HEAD 2>/dev/null | tail -5
```

---

## Step 1 — What Shipped

List every change landed in the last sprint:

```bash
git log --oneline --since="7 days ago" --format="%h %s" 2>/dev/null
```

Categorize each commit:
- **TASK** -- new incident scenario added
- **GRADER** -- grader logic changed
- **ENV** -- core_env.py changed
- **SERVER** -- server/app.py changed
- **DEPLOY** -- Dockerfile or openenv.yaml changed
- **DOCS** -- README, ARCHITECTURE, AGENTS, CLAUDE changed
- **TEST** -- scratch/ or test scripts changed
- **FIX** -- bug fix

---

## Step 2 — Score Metrics

Run current grader scores across all tasks:

```bash
python -c "
from core_env import IncidentOpsEnv
from grader import grade_episode
import tasks.task_easy as easy_mod
import tasks.task_medium as medium_mod
import tasks.task_hard as hard_mod

for task_id, mod in [('easy', easy_mod), ('medium', medium_mod), ('hard', hard_mod)]:
    env = IncidentOpsEnv()
    env.reset(task_id=task_id)
    s = env.internal_state
    # Simulate perfect run
    s.evidence_map.alerts_viewed = True
    for svc in getattr(mod, 'RELEVANT_LOG_SERVICES', set()):
        s.evidence_map.logs_viewed[svc] = True
        s.evidence_map.metrics_checked[svc] = True
    s.evidence_map.deploys_checked = True
    s.severity_classified_correctly = True
    s.hypothesis_correct = True
    s.mitigation_correct = True
    s.mitigation_applied = 'optimal'
    s.communication_posted = True
    if s.requires_escalation:
        s.escalation_correct = True
    s.resolved = True
    s.episode_step = int(s.max_steps * 0.5)  # 50% budget used
    result = grade_episode(s, mod)
    print(f'{task_id}: {result.total:.4f} ({result.summary.split(chr(10))[0]})')
"
```

---

## Step 3 — What Worked

List 3-5 things that went well this sprint:
- Which tasks are cleanest (high optimal scores, clear evidence chains)?
- Which architectural decisions proved correct?
- What testing caught bugs early?

---

## Step 4 — What Didn't Work

List 3-5 things to improve:
- Were any task scores wrong until we fixed something?
- Did ASCII compliance issues delay a deployment?
- Was any evidence chain confusing or ambiguous?
- Any edge cases in the grader that surprised us?

---

## Step 5 — Session Statistics

```bash
echo "Total commits:"
git rev-list --count HEAD

echo "Lines changed (last sprint):"
git diff --stat HEAD~5..HEAD 2>/dev/null | grep "changed" | tail -1

echo "Task files:"
ls -la tasks/task_*.py

echo "Test results:"
python scratch/test_evals.py 2>&1 | grep -E "PASS|FAIL|Error"
```

---

## Step 6 — Next Sprint Planning

Based on what shipped and what broke, propose the next sprint priorities:

**Priority 1 (ship next):** [most important task/fix]
**Priority 2:** [second priority]
**Priority 3:** [nice to have]

For each priority, estimate effort:
- Task data file: 30 min
- Grader change: 1 hour
- New action type: 2 hours
- Server endpoint: 1 hour
- Architecture change: 4+ hours

---

## Step 7 — Retro Report

```
=== IncidentOpsEnv Sprint Retro ===
Date: [timestamp]
Sprint: [dates or sprint number]

WHAT SHIPPED:
- [list commits by category]

SCORE METRICS:
  easy:   [optimal score]
  medium: [optimal score]
  hard:   [optimal score]

LINES CHANGED: [+X -Y]
COMMITS: [N]

WHAT WORKED:
1. [thing 1]
2. [thing 2]
3. [thing 3]

WHAT TO IMPROVE:
1. [thing 1]
2. [thing 2]
3. [thing 3]

OPERATIONAL LEARNINGS:
(Things to remember for next time)
- [learning 1]
- [learning 2]

NEXT SPRINT PRIORITIES:
1. [P1] -- [time estimate]
2. [P2] -- [time estimate]
3. [P3] -- [time estimate]
```

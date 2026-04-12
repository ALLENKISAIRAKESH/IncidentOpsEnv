# IncidentOpsEnv — AI Engineering Workflow
# Adapted from garrytan/gstack for Antigravity + IncidentOpsEnv

IncidentOpsEnv is a deterministic, step-based SRE incident response simulator.
AI agents are evaluated against real-world production scenarios using a
7-dimension rule-based grader.

This file defines specialist roles for AI agents working IN this project
(building/maintaining it), NOT for agents solving incident tasks.

---

## Available Skills

Skills live in `.agents/skills/`. Invoke them by name (e.g., `/sre-office-hours`).

| Skill | Role | What it does |
|-------|------|-------------|
| `/sre-office-hours` | SRE Lead | Start here. Reframes the incident scenario before you add a task. |
| `/task-review` | Task Designer | Reviews new incident tasks for realism and solvability. |
| `/grader-audit` | QA Lead | Audits grader weights, edge cases, and score fairness. |
| `/env-review` | Eng Manager | Reviews core_env.py for correctness, concurrency, and edge cases. |
| `/incident-qa` | QA Agent | Runs all 3 tasks end-to-end and validates step budgets + scores. |
| `/score-review` | Score Auditor | Reviews grade_episode() output against expected baselines. |
| `/deploy-check` | Release Eng | Validates Dockerfile, openenv.yaml, and HuggingFace deployment. |
| `/retro` | Team Lead | Post-sprint retrospective across all incident tasks. |
| `/investigate` | Debugger | Root-cause investigation for broken tasks or wrong scores. |
| `/carefully` | Safety Guard | Warns before destructive changes (dropping tasks, resetting state). |

---

## Specialist Roles Defined

### SRE Lead (/sre-office-hours)
Acts as a senior SRE reviewing a new incident scenario proposal.
- Challenges realism: "Would this actually cause these symptoms in prod?"
- Checks detectability: "Can an AI agent reasonably find this from the evidence?"
- Validates step budget: "Is MAX_STEPS fair for the intended difficulty?"
- Outputs a design doc that feeds into /task-review.

### Task Designer (/task-review)
Reviews task_*.py files for internal consistency.
- Correct evidence chain: alerts -> logs -> metrics -> root cause
- HARMFUL_MITIGATIONS are plausible wrong answers (not impossible ones)
- RELEVANT_LOG_SERVICES match what the grader uses for evidence scoring
- factory function returns consistent (Observation, InternalState) pair

### QA Lead (/incident-qa)
Runs all 3 tasks with a scripted optimal agent, then a suboptimal agent.
- Verifies easy task score > 0.85 with optimal path
- Verifies hard task score < 0.85 without domain knowledge
- Checks score clamping: final score in (0.01, 0.99)
- Validates no crashes on edge-case actions (None target, spam, wrong type)

### Score Auditor (/score-review)
Reviews grader.py component weights and scoring logic.
- WEIGHTS must sum to 1.0 (assert is in place, verify it runs)
- Evidence score partial credit logic is correct
- Efficiency score degrades smoothly from 60% -> 100% budget use
- Safety score starts at 1.0 and penalizes harmful mitigations

### Eng Manager (/env-review)
Reviews core_env.py for production correctness.
- Session isolation (SUPPORTS_CONCURRENT_SESSIONS = True)
- No shared state between episodes
- All action types dispatch correctly
- Spam detection threshold is appropriate

### Release Engineer (/deploy-check)
Validates deployment artifacts.
- Dockerfile builds without errors
- openenv.yaml spec_version, tasks, and app match actual code
- HuggingFace Space URL is reachable and returns 200
- All files are ASCII-clean (no emoji or non-ASCII in code files)

---

## Build Commands

```bash
# Run all task grader tests
python scratch/test_evals.py

# Run verbose grader breakdown
python scratch/manual_test_verbose.py

# Run the AI inference agent
python inference.py --task easy
python inference.py --task medium
python inference.py --task hard

# Start the FastAPI server locally
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload

# Build Docker image
docker build -t incident-ops-env .
docker run -p 7860:7860 incident-ops-env
```

---

## Key Conventions

- `core_env.py` is the single source of truth for episode logic. Never duplicate
  reward constants in task files.
- Task files (`tasks/task_*.py`) are DATA files — they hold static evidence,
  not episode logic.
- `grader.py` is stateless — it reads InternalState and returns a GradeResult.
  Never call it mid-episode; only call at done=True.
- RELEVANT_LOG_SERVICES in each task module must match what the agent needs
  to view for full evidence score.
- HARMFUL_MITIGATIONS must be (ActionType, target_str_or_enum) tuples.
- Score range is strictly (0.01, 0.99) per OpenEnv spec. The clamp is in
  grade_episode(), not in the env.
- All Python files must be ASCII-only for HuggingFace Space compatibility.

---

## Sprint Order for New Features

Think -> Design -> Build -> Test -> Grade -> Deploy -> Retro

1. /sre-office-hours   — define the new incident scenario
2. /task-review        — validate task data is consistent
3. Implement task_*.py — add static evidence data
4. /incident-qa        — run end-to-end tests on all steps
5. /score-review       — verify grader handles new task correctly
6. /env-review         — check core_env.py handles edge cases
7. /deploy-check       — validate Docker + openenv.yaml + HF push
8. /retro              — retrospective on what worked and what didn't

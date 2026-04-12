# CLAUDE.md — IncidentOpsEnv
# Adapted from garrytan/gstack for Antigravity + IncidentOpsEnv

## Project Context
IncidentOpsEnv is a deterministic, step-based SRE incident response simulator
built for the OpenEnv hackathon. It evaluates AI agents against 3 production
incident scenarios (easy / medium / hard) using a 7-dimension rule-based grader.

HuggingFace Space: https://huggingface.co/spaces/allenkisairakesh/incident-ops-env
GitHub: ALLENKISAIRAKESH/IncidentOpsEnv

---

## Commands

```bash
# Test all grader logic (fast, free)
python scratch/test_evals.py

# Verbose grader breakdown with per-dimension scores
python scratch/manual_test_verbose.py

# Run AI inference agent on a task
python inference.py --task easy
python inference.py --task medium
python inference.py --task hard

# Start dev server
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload

# Docker build + run
docker build -t incident-ops-env .
docker run -p 7860:7860 incident-ops-env
```

Run `python scratch/test_evals.py` before every commit — it is fast (<5s) and free.
Run `python inference.py --task easy` before shipping to validate end-to-end behavior.

---

## Project Structure

```
scalar-space/
├── core_env.py           # Main environment (episode logic, action dispatch, rewards)
├── grader.py             # Rule-based grader (7-dimension scorer, stateless)
├── models.py             # Pydantic models (Action, Observation, InternalState, etc.)
├── inference.py          # AI agent runner (OpenAI-compatible endpoint)
├── client.py             # Python client for the OpenEnv HTTP API
├── app.py                # Gradio dashboard (HuggingFace UI)
├── openenv.yaml          # OpenEnv spec (spec_version, tasks, runtime)
├── Dockerfile            # HuggingFace Space deployment
├── pyproject.toml        # Package config
├── requirements.txt      # Runtime dependencies
│
├── server/               # FastAPI server (OpenEnv HTTP interface)
│   ├── app.py            # FastAPI app with /reset, /step, /grade endpoints
│   └── __init__.py
│
├── tasks/                # Task data files (static evidence per incident)
│   ├── task_easy.py      # DB pool exhaustion (payment-api)
│   ├── task_medium.py    # Bad deploy regression (checkout-service)
│   ├── task_hard.py      # Feature flag misconfiguration (auth-v2)
│   └── utils.py          # Shared helpers (generate_noise_logs)
│
├── scratch/              # Local test scripts (not deployed)
│   ├── test_evals.py     # Quick pass/fail for all 3 tasks
│   └── manual_test_verbose.py  # Verbose grader output
│
└── .agents/              # AI agent skills (GStack-style)
    └── skills/
        ├── sre-office-hours/SKILL.md
        ├── task-review/SKILL.md
        ├── grader-audit/SKILL.md
        ├── env-review/SKILL.md
        ├── incident-qa/SKILL.md
        ├── score-review/SKILL.md
        ├── deploy-check/SKILL.md
        ├── retro/SKILL.md
        └── investigate/SKILL.md
```

---

## Architecture Principles

### Single Source of Truth
- `core_env.py` owns ALL episode logic. Reward constants live here only.
- Task files (`tasks/task_*.py`) are PURE DATA — alerts, logs, metrics, deploys.
- `grader.py` is STATELESS — takes InternalState, returns GradeResult. No side effects.
- `models.py` defines ALL types. Never create inline dicts for structured data.

### Session Isolation
- `SUPPORTS_CONCURRENT_SESSIONS = True` is set in IncidentOpsEnv.
- Every call to `reset()` creates a NEW InternalState — no shared mutation.
- The server manages session IDs; the env has no knowledge of sessions.

### Determinism
- All task data is STATIC — hardcoded in task_*.py files.
- Noise logs use a fixed seed via `generate_noise_logs()`.
- No randomness. Same action sequence = same reward, every time.

### Score Range
- Final score is clamped to (0.01, 0.99) in `grade_episode()`.
- Per-step rewards are unbounded but the final grade is clamped.
- WEIGHTS in grader.py must sum to 1.0 (assert enforces this).

---

## Platform-Agnostic Design
Never hardcode:
- HuggingFace Space URL in source code (use env vars or config)
- API keys or model names in source (use env vars)
- Absolute file paths (use relative imports and `__file__`)

For env vars, read from environment:
```python
import os
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
```

---

## Python Code Rules

### ASCII-Only
All `.py` files must be ASCII-only. HuggingFace Spaces uses a charmap codec
that crashes on non-ASCII (emoji, smart quotes, etc.).

- NO emoji in source files, docstrings, or string literals
- Use `--` for dashes in comments, not em-dashes
- Use plain ASCII arrows: `->` not `→`

Run this to check before deploying:
```bash
python -c "
import os
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ['.git', '.venv', '__pycache__', 'node_modules']]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                open(path, encoding='ascii').read()
            except UnicodeDecodeError as e:
                print(f'NON-ASCII: {path}: {e}')
"
```

### Imports
- All task files import from `models` (not `..models`)
- Always use `from __future__ import annotations` at the top of files
  that use forward references in type hints.

### Error Messages
Make error messages actionable for AI agents:
- BAD: "Invalid action"
- GOOD: "classify_severity requires a severity level. Valid values: low, medium, high, critical"

---

## Adding a New Task

1. Create `tasks/task_newname.py` following the existing pattern:
   - Define INCIDENT_ID, TASK_NAME, MAX_STEPS
   - Define ALERTS, LOGS, METRICS, DEPLOYS, FEATURE_FLAGS, DEPENDENCY_MAP
   - Define RELEVANT_LOG_SERVICES (set of service name strings)
   - Define HARMFUL_MITIGATIONS (set of (ActionType, target) tuples)
   - Implement `get_newname_task()` returning (Observation, InternalState)
   - Implement `get_alerts()`, `get_logs()`, `get_metrics()`, `get_deploys()`,
     `get_feature_flags()`, `get_dependency_map()`

2. Add to `core_env.py`:
   - Add "newname" to `VALID_TASKS` tuple

3. Add to `openenv.yaml`:
   ```yaml
   - id: newname
     name: New Task Name
   ```

4. Update `tasks/__init__.py` if needed.

5. Run `python scratch/test_evals.py` to verify.

---

## Commit Style

Every commit should be a single logical change. Split these into separate commits:
- Task data file addition vs. grader logic changes
- New action type vs. model changes
- Server endpoint addition vs. env logic changes

Examples:
- `feat(tasks): add task_medium -- bad deploy regression scenario`
- `fix(grader): correct efficiency score scaling for 60-100% budget`
- `feat(env): add SCALE_SERVICE action dispatch`
- `docs: update README with task_medium grading table`

---

## Testing Protocol

Before every commit:
```bash
python scratch/test_evals.py   # All 3 tasks pass
```

Before every deploy:
```bash
python inference.py --task easy     # End-to-end with real AI agent
python inference.py --task medium
python inference.py --task hard
docker build -t incident-ops-env . && docker run -p 7860:7860 incident-ops-env
```

---

## AI Effort Compression (GStack Philosophy)

| Task type | Human team | AI+tools | Compression |
|-----------|-----------|----------|-------------|
| New task data file | 2 hours | 5 min | ~24x |
| Grader logic change | 4 hours | 10 min | ~24x |
| End-to-end test suite | 1 day | 20 min | ~24x |
| New action type | 3 hours | 10 min | ~18x |
| Architecture change | 2 days | 4 hours | ~12x |

Completeness is cheap. Don't cut corners on test coverage or error handling
when the full implementation is a "lake" (achievable), not an "ocean" (months).

---

## Search Before Building

Before adding a new feature:
1. Search existing code: does `core_env.py` already handle this?
2. Check `models.py`: does the type already exist?
3. Check `tasks/utils.py`: is there a shared helper for this pattern?

Three knowledge layers: OpenEnv spec (Layer 1), FastAPI/Pydantic docs (Layer 2),
first-principles SRE reasoning (Layer 3). Prize Layer 3 — real incident patterns
beat framework patterns in this domain.

---

## gstack Integration
This project uses a GStack-inspired skill system adapted for SRE incident ops.
Skills are in `.agents/skills/`. Each skill is a Markdown prompt template.

Available skills (see AGENTS.md for full descriptions):
- /sre-office-hours
- /task-review
- /grader-audit
- /env-review
- /incident-qa
- /score-review
- /deploy-check
- /retro
- /investigate
- /carefully

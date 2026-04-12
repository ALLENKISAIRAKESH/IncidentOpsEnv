# /deploy-check — Deployment Validation for HuggingFace Space
# Role: Release Engineer (validates all deployment artifacts before push)

You are the Release Engineer for IncidentOpsEnv. Your job is to verify
that everything is ready for a clean HuggingFace Space deployment.
No guessing. Run every check. Report pass/fail for each.

---

## Step 0 — Pre-flight

```bash
echo "=== Deploy Check ==="
echo "Target: HuggingFace Space (allenkisairakesh/incident-ops-env)"
git status
git log --oneline -5
```

---

## Step 1 — ASCII Compliance Check (CRITICAL)

HuggingFace Spaces uses charmap codec. One non-ASCII character = deployment crash.

```bash
python -c "
import os, sys
errors = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ['.git', '.venv', '__pycache__', 'node_modules']]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                open(path, encoding='ascii').read()
            except UnicodeDecodeError as e:
                errors.append(f'{path}: {e}')
if errors:
    print('[FAIL] NON-ASCII FOUND:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print('[PASS] All .py files are ASCII-clean')
"
```

If this fails, STOP. Fix the non-ASCII files before continuing.

---

## Step 2 — openenv.yaml Validation

```bash
python -c "
import yaml, sys
with open('openenv.yaml') as f:
    config = yaml.safe_load(f)
print('spec_version:', config.get('spec_version'))
print('name:', config.get('name'))
print('runtime:', config.get('runtime'))
print('app:', config.get('app'))
print('port:', config.get('port'))
tasks = config.get('tasks', [])
task_ids = [t['id'] for t in tasks]
print('task_ids:', task_ids)

# Validate against actual task files
import os
actual_tasks = []
for f in os.listdir('tasks'):
    if f.startswith('task_') and f.endswith('.py') and f != 'task_utils.py':
        actual_tasks.append(f.replace('task_', '').replace('.py', ''))

actual_tasks = sorted(actual_tasks)
config_tasks = sorted(task_ids)
if actual_tasks == config_tasks:
    print('[PASS] openenv.yaml task IDs match task files:', actual_tasks)
else:
    print('[FAIL] Mismatch:')
    print('  Config tasks:', config_tasks)
    print('  Actual files:', actual_tasks)
    sys.exit(1)
"
```

---

## Step 3 — Docker Build Test

```bash
docker build -t incident-ops-env-check . 2>&1 | tail -20
echo "Exit code: $?"
```

If build fails:
- Check Dockerfile for syntax errors
- Check requirements.txt for version conflicts
- Check that all imports in app.py / server/app.py resolve

---

## Step 4 — Docker Runtime Test

```bash
docker run --rm -p 7860:7860 -d --name ioe-check incident-ops-env-check
sleep 5
curl -s http://localhost:7860/health || curl -s http://localhost:7860/ | head -100
docker stop ioe-check
```

If runtime fails:
- Check uvicorn startup in Dockerfile CMD
- Check server/app.py for startup errors
- Check that openenv.yaml `app` field matches actual FastAPI app path

---

## Step 5 — OpenEnv Endpoint Check

```bash
# Test the reset endpoint
curl -s -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}' | python -m json.tool
```

Expected: JSON with `incident_id`, `remaining_step_budget`, etc.

```bash
# Test with session ID (from above response)
SESSION_ID="the-session-id-from-above"
curl -s -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"action\": {\"action_type\": \"view_alerts\"}}" \
  | python -m json.tool
```

---

## Step 6 — Grader Weights Assertion

```bash
python -c "
from grader import WEIGHTS
total = sum(WEIGHTS.values())
print(f'Weights total: {total:.10f}')
assert abs(total - 1.0) < 1e-9, f'Weights do not sum to 1.0: {total}'
print('[PASS] Grader weights sum to 1.0')
"
```

---

## Step 7 — Core Test Suite

```bash
python scratch/test_evals.py
```

All 3 tasks must pass. If any fail, DO NOT deploy.

---

## Step 8 — Pre-Deploy Git Check

```bash
# Check no binary files are staged
git diff --cached --name-only | python -c "
import sys
binary_extensions = ['.pyc', '.pkl', '.h5', '.bin', '.so', '.dll', '.pyd']
staged = sys.stdin.read().strip().split('\n')
bad = [f for f in staged if any(f.endswith(ext) for ext in binary_extensions)]
if bad:
    print('[FAIL] Binary files staged:', bad)
    sys.exit(1)
else:
    print('[PASS] No binary files staged')
"
```

```bash
# Check requirements.txt has no git+ or local paths
python -c "
with open('requirements.txt') as f:
    reqs = f.readlines()
bad = [r.strip() for r in reqs if r.strip().startswith(('git+', '/', './', '../'))]
if bad:
    print('[FAIL] Invalid requirements:', bad)
else:
    print('[PASS] requirements.txt is clean')
"
```

---

## Step 9 — Deploy Report

```
=== Deploy Check Report ===
Date: [timestamp]
Branch: [git branch name]
Commit: [git commit hash]

CHECKS:
  [PASS/FAIL] ASCII compliance (all .py files)
  [PASS/FAIL] openenv.yaml task IDs match task files
  [PASS/FAIL] Docker build
  [PASS/FAIL] Docker runtime (health check)
  [PASS/FAIL] OpenEnv /reset endpoint
  [PASS/FAIL] OpenEnv /step endpoint  
  [PASS/FAIL] Grader weights sum to 1.0
  [PASS/FAIL] Core test suite (test_evals.py)
  [PASS/FAIL] No binary files staged
  [PASS/FAIL] requirements.txt clean

OVERALL: [ALL PASS -- Ready to deploy | X FAILURES -- Do NOT deploy]

ISSUES:
- [list any failures with details]

NEXT STEP:
[openenv push | Fix issues first]
```

---

## Deploy Command (only after ALL PASS)

```bash
openenv push
```

After push, verify HuggingFace Space is live:
```bash
curl -s https://allenkisairakesh-incident-ops-env.hf.space/health | python -m json.tool
```

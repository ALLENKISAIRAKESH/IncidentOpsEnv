# ARCHITECTURE.md — IncidentOpsEnv
# Adapted from garrytan/gstack for Antigravity + IncidentOpsEnv

This document explains WHY IncidentOpsEnv is built the way it is.
For setup and commands, see CLAUDE.md. For AI agent roles, see AGENTS.md.

---

## The Core Idea

IncidentOpsEnv gives AI agents a structured incident response simulation with
persistent episodic state and deterministic grading. The hard part is keeping
the environment fully deterministic (same action = same reward) while supporting
concurrent sessions for benchmarking multiple agents simultaneously.

```
AI Agent
   |
   | HTTP (OpenEnv protocol)
   v
FastAPI Server (server/app.py)
   |
   | Python call: env.reset() / env.step(action) / env.grade()
   v
IncidentOpsEnv (core_env.py)
   |
   |--- imports task module dynamically (tasks/task_easy|medium|hard.py)
   |--- calls grader at episode end (grader.py)
   |--- uses typed models (models.py)
   v
GradeResult (0.01 - 0.99, 7 dimensions)
```

First call to /reset creates a session and returns initial Observation.
Each /step call dispatches one action and returns updated Observation + reward.
/grade (or done=True in step) triggers grade_episode() and returns final score.

---

## Why This Layered Design

### Layer 1: Task Files (Static Data)
`tasks/task_*.py` hold ONLY static evidence data:
- ALERTS, LOGS, METRICS, DEPLOYS, FEATURE_FLAGS, DEPENDENCY_MAP
- Ground truth: root_cause, correct_mitigation, correct_mitigation_target, correct_severity
- Grader hints: RELEVANT_LOG_SERVICES, HARMFUL_MITIGATIONS

Why static? Reproducibility. The same incident plays out identically every
run. An AI agent that discovers the root cause is rewarded for real diagnostic
reasoning, not lucky random paths. This is intentional — we're evaluating
REASONING quality, not exploration efficiency.

### Layer 2: Environment (Episode Logic)
`core_env.py` owns ALL state transitions:
- Reward constants (R_CORRECT_SEVERITY, R_HARMFUL_MITIGATION, etc.)
- Spam detection (repeated action counter -> SPAM_THRESHOLD)
- Action dispatch (_dispatch -> _do_* methods)
- Done detection (resolved OR step budget exhausted)
- State mutation (InternalState tracks everything the grader needs)

Why a single file? Locality. Every reward decision is in one place.
When you add a new action type, you add ONE dispatch branch and ONE handler.

### Layer 3: Grader (Stateless Scoring)
`grader.py` is a PURE FUNCTION over InternalState:
- Takes: (InternalState, task_module) -> GradeResult
- No side effects. No DB. No global state.
- Called exactly once per episode at done=True.

Why stateless? Testability. You can construct any InternalState in a test
and verify score output without running a full episode. See scratch/test_evals.py.

### Layer 4: Server (HTTP Protocol)
`server/app.py` implements the OpenEnv protocol over FastAPI:
- POST /reset  -> calls env.reset(task_id)
- POST /step   -> calls env.step(action) 
- GET  /grade  -> returns final grade
- Session management: UUID -> IncidentOpsEnv instance mapping

Why FastAPI? Type safety + automatic OpenAPI docs. Pydantic models from
models.py are shared between the env and the server — same Action type
used everywhere.

---

## Concurrency Model

```
Client A                        Server
--------                        ------
POST /reset {task: "easy"}  ->  session_id = uuid4()
                                sessions[session_id] = IncidentOpsEnv("easy")
                                sessions[session_id].reset()
<- {session_id: "abc123", obs: ...}

Client B
POST /reset {task: "hard"}  ->  session_id = uuid4()
                                sessions[session_id] = IncidentOpsEnv("hard")
                                sessions[session_id].reset()
<- {session_id: "def456", obs: ...}

Client A
POST /step {session_id: "abc123", action: ...}
                                env = sessions["abc123"]
                                env.step(action)  # fully isolated, no shared state
```

SUPPORTS_CONCURRENT_SESSIONS = True means the OpenEnv framework knows it can
run multiple sessions. Each IncidentOpsEnv instance has its OWN InternalState —
there is zero shared mutable state between sessions.

Session expiry: 30 min idle (configured in server/app.py).

---

## State Machine per Episode

```
Initial (after reset)
   |
   | action -> _dispatch()
   v
Running (0 < step < max_steps)
   |
   |-- RESOLVE_INCIDENT (mitigation applied) --> Resolved (done=True, grade computed)
   |-- RESOLVE_INCIDENT (no mitigation)      --> Premature Resolve (done=True, penalty)
   |-- step >= max_steps                     --> Timeout (done=True, -0.10 penalty)
   |-- any other action                      --> Running (reward applied, step++)
```

The state machine is fully encoded in `step()` in core_env.py.
`InternalState.resolved` is the single terminal flag.
`InternalState.premature_resolved` distinguishes resolve-without-mitigation.

---

## Reward Architecture

Two-phase reward design (inspired by SRE practice):

**Per-step rewards** (immediate feedback, encourages correct investigation order):
```
view new evidence:        +0.05
correct severity:         +0.10
correct root cause:       +0.10
correct mitigation:       +0.20
status update posted:     +0.05
correct escalation:       +0.05
incident resolved:        +0.20

wrong severity:           -0.05
harmful mitigation:       -0.20
premature resolve:        -0.15
repeated action (spam):   -0.02
step budget exhausted:    -0.10
```

**Final grade** (7-dimension weighted score, computed once at done=True):
```
evidence_score       0.15  -- viewed alerts + relevant logs + metrics
severity_score       0.15  -- classified correct severity
cause_score          0.20  -- correct root cause hypothesis
mitigation_score     0.25  -- right action on right target
communication_score  0.10  -- status update + escalation (if required)
efficiency_score     0.10  -- resolved within 60% of step budget = full credit
safety_score         0.05  -- no harmful mitigations (starts at 1.0)
```

Why TWO reward signals? Per-step rewards shape agent behavior in real-time
(dense signal). Final grade is the true evaluation metric (sparse but holistic).
An agent optimizing only for per-step rewards could spam evidence-gathering
without resolving. The efficiency score in the final grade penalizes this.

---

## Evidence Chain Design

Each task is designed around a realistic investigation path:

```
Easy (DB Pool Exhaustion):
  view_alerts -> [ALT-8821, ALT-8822]  # payment-api + DB both firing
  view_logs(payment-api) -> HikariPool exhausted messages
  view_logs(database) -> pool limit reached (50/50)
  check_metrics(payment-api) -> error_rate 38.4%, latency 31s
  classify_severity(high)
  hypothesize_root_cause(db_connection_pool_exhaustion)
  restart_service(payment-api)  # correct mitigation
  post_status_update
  resolve_incident

Medium (Bad Deploy):
  view_alerts -> checkout-service errors
  check_recent_deploys -> bad deploy 2h ago
  view_logs(checkout-service) -> NullPointerException on new code path
  classify_severity(high)
  hypothesize_root_cause(bad_deploy_regression)
  rollback_deploy(checkout-service)  # correct mitigation
  post_status_update
  resolve_incident

Hard (Feature Flag Cascade):
  view_alerts -> auth failures (indirect symptoms)
  inspect_feature_flags -> auth-v2 at 100% rollout (suspicious change)
  view_logs(auth-service) -> JWT validation failures under auth-v2 path
  view_dependency_map -> auth-service -> payment-api -> checkout
  classify_severity(critical)
  hypothesize_root_cause(feature_flag_misconfiguration)
  disable_feature_flag(auth-v2)  # correct mitigation
  escalate_team(security-team)   # hard task requires escalation
  post_status_update
  resolve_incident
```

The hard task requires more evidence steps AND an escalation, testing both
diagnostic depth and communication protocol.

---

## Error Philosophy

Error messages are for AI agents, not humans. Every error must be actionable:

BAD:  "Invalid action"
GOOD: "restart_service requires a target_service. Valid: payment-api, checkout-service, auth-service"

BAD:  "Wrong hypothesis"
GOOD: "Root cause hypothesis 'cpu_spike' -- incorrect. Continue investigating."

BAD:  "Episode done"
GOOD: "Episode is already done. Call reset() to start a new episode."

The agent should read the error and know what to do next without human help.
This is especially important because inference.py runs fully autonomously.

---

## The OpenEnv Protocol Fit

OpenEnv expects:
- Environment class inherits from `openenv.core.env_server.interfaces.Environment`
- `reset(task_id) -> Observation`
- `step(action) -> Observation`
- `get_task_ids() -> list[str]`
- `get_metadata() -> dict`
- `state -> State` (episode_id + step_count)
- `close() -> None`

IncidentOpsEnv satisfies all of these. The `step()` return type is typed as
`Observation` (not `StepResult`) because OpenEnv reads the observation object
for done, reward, and final_score fields.

The `Observation` model contains:
- `done: bool`
- `reward: float` (per-step scalar)
- `final_score: Optional[float]` (only set when done=True)

This dual-use of Observation matches OpenEnv's design — the observation IS
the full state exposed to the agent, including reward feedback.

---

## Design Decisions and Trade-offs

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| Task data format | Python files (static) | YAML/JSON | Type safety, Pydantic models |
| Grader architecture | Stateless function | In-env scoring | Testability |
| Session management | In-memory dict | Redis/DB | Simplicity (30min timeout) |
| Action types | Typed Enum | Free-text strings | Prevents agent typos, validates at parse time |
| Grader call timing | Only at done=True | Every step | Avoid penalizing partial episodes |
| Score range | (0.01, 0.99) | [0, 1] | OpenEnv spec requirement |
| Concurrency | Per-instance state | Global state | Thread safety |
| Noise logs | Fixed fake logs | Real prod logs | Privacy + reproducibility |

---

## Anti-Patterns to Avoid

1. **Global state in task files** — task_*.py must have ZERO global mutable state.
   ALERTS, LOGS, METRICS, etc. are module-level CONSTANTS, never modified at runtime.

2. **Reward logic in task files** — R_* constants belong in core_env.py only.
   Task files must not import or use reward values.

3. **Calling grade_episode() mid-episode** — the grader assumes the episode is
   complete. Calling it with a partial InternalState gives wrong scores.

4. **Non-ASCII in .py files** — HuggingFace Space deployment uses charmap codec.
   One emoji = deployment crash. Run the ASCII check before every deploy.

5. **Sharing InternalState between sessions** — factory functions (get_easy_task(), etc.)
   must return a NEW InternalState object each time. Never cache or reuse state objects.

6. **Hardcoding session IDs** — sessions are UUIDs managed by the server.
   The env has no knowledge of session IDs.

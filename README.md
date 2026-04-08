---
title: IncidentOpsEnv
emoji: 🚨
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
---

# IncidentOpsEnv 🚨

A production incident response simulation environment built for the OpenEnv framework.

## Motivation
SRE (Site Reliability Engineering) is a high-stakes, high-complexity domain where AI agents must bridge the gap between **raw telemetry** (logs/metrics) and **logical remediation** (rolling back, scaling). Unlike simple web-navigation, `IncidentOpsEnv` requires an agent to form hypotheses, communicate with human-like templates, and make safety-critical decisions. This environment provides a reproducible sandbox to train and evaluate the next generation of "AI-SREs."

## Tasks & Difficulty

| Task ID | Name | Difficulty | Description |
| :--- | :--- | :--- | :--- |
| `easy` | DB Pool Leak | **Easy** | A database connection pool exhaustion. Requires basic log checking and a service restart. |
| `medium` | Deploy Regression | **Medium** | A bad deployment causing checkout failures. Requires checking Recent Deploys and performing a Rollback. |
| `hard` | Cascade Failure | **Hard** | A feature flag rollout causing a multi-service cascade. Requires dependency mapping and targeted flag disabling. |

## Environment Architecture & Reward Logic
- **Partial Progress Signal**: Unlike binary (0 or 1) environments, `IncidentOpsEnv` rewards agents for each correct step:
    - `+0.05` for viewing relevant evidence (alerts, logs).
    - `+0.10` for correct severity classification.
    - `+0.20` for applying the correct mitigation.
- **Safety Penalties**: Agents are penalized `-0.20` for "harmful mitigations" (e.g., restarting the wrong production database).
- **Communication**: Extra credit for posting status updates and escalating to the correct Ops team.
- **Deterministic Engine**: Built on typed `pydantic` models with zero-randomness in outcomes for reproducible benchmarking.

## Observation and Action Spaces
- **Observation Space**: `obs.incident_summary`, `obs.known_alerts`, `obs.retrieved_logs`, `obs.affected_services`. (See `models.Observation` for strictly typed Schema).
- **Action Space**: `action_type` (Enum spanning 15 SRE verbs like `view_logs`, `scale_service`), `target_service`, `severity`, `hypothesis`. (See `models.Action`).

## Baseline Scores
- **Easy**: 0.95 (GPT-4o), 0.80 (GPT-4o-mini)
- **Medium**: 0.85 (GPT-4o), 0.60 (GPT-4o-mini)
- **Hard**: 0.70 (GPT-4o), 0.20 (GPT-4o-mini)

## Usage & Inference
A baseline inference script `inference.py` is included to interact with the environment. Configure the required OpenEnv execution variables:

```sh
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o"
export HF_TOKEN="hf_your_hugging_face_token"

python inference.py --task easy
```

## Reproducibility & Docker
Compatible with Hugging Face Spaces (Docker SDK). You can build and run it directly:
```sh
docker build -t incident-ops-env .
docker run -it -e OPENAI_API_KEY=$OPENAI_API_KEY incident-ops-env
```

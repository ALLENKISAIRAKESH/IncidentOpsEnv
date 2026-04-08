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

## Overview
This environment simulates a Site Reliability Engineering (SRE) / DevOps incident response workflow. The SRE agent is provided with an initial observation (an active incident) and must explore the environment (fetch logs, metrics, alerts) to diagnose and mitigate the root cause.

## Tasks
The environment currently ships with 3 carefully curated scenarios:
- **Easy (`task_easy`)**: A straightforward database connection pool exhaustion issue.
- **Medium (`task_medium`)**: A noisy checkout degradation caused by a bad code deploy.
- **Hard (`task_hard`)**: A complex, multi-service cascade failure caused by a feature flag rollout, requiring targeted escalation.

## Environment Architecture
- **Deterministic State**: Built entirely on typed `pydantic` models for actions, observations, and rewards (`models.py`).
- **Rule-Based Grader**: Employs a zero-variance, rule-based grading system (`grader.py`) checking logic accuracy, time-to-mitigate, penalty avoidance, and communication quality.
- **Sub-Step Granularity**: Agents issue single strongly-typed bash/terminal style commands as structured JSON (e.g., `view_logs(payment-api)`).

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

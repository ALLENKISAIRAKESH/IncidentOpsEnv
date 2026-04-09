---
title: IncidentOpsEnv
emoji: fire
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# IncidentOpsEnv: Production-Grade SRE Simulation

[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compliant-success)](https://github.com/openenv/openenv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

IncidentOpsEnv is a high-fidelity Site Reliability Engineering (SRE) simulator designed to evaluate the troubleshooting and remediation capabilities of AI agents. It mirrors real-world production environments, complete with microservices, dependency cascades, and signal noise.

---

## System Architecture

```mermaid
graph TD
    User["Users"] --> LB["Load Balancer"]
    LB --> Frontend["Frontend Service"]
    Frontend --> Checkout["Checkout Service"]
    Frontend --> Auth["Auth Service"]
    Checkout --> Orders["Orders Service"]
    Orders --> Inventory["Inventory Service"]
    Orders --> DB[("(RDS) Postgres")]
    Inventory --> Redis["Redis Cache"]
```

## Task Matrix

| Task ID | Scenario | Primary Challenge | Target Remediation |
| :--- | :--- | :--- | :--- |
| easy | DB Pool Exhaustion | Traffic Spike | scale_service (DB) |
| medium | Deploy Regression | Buggy Code in Checkout | rollback_deploy (Checkout) |
| hard | Multi-service Cascade | Dependency failure | scale_service + restart |

## Reward Signal Architecture

Our environment uses Shaped Rewards to provide granular feedback to agents:

* Discovery (+0.05): Viewing logs or alerts that reveal root cause evidence.
* Correct Hypothesis (+0.20): Formulating a root cause that matches environment state.
* Failed Attempt (-0.15): Trying to resolve without fixing the underlying issue.
* Resolution (+0.99): Successfully returning the system to target SLIs.

## Getting Started

### Prerequisites
* Python 3.10+
* pip install -r requirements.txt

### Local Execution
```bash
python inference.py --task easy
```

### Manual Dashboard
Once deployed to a Hugging Face Space, access the visual playground at:
https://huggingface.co/spaces/<user>/incident-ops-env/

---

## Compliance Metadata

* Runtime: FastAPI / Uvicorn
* Interface: OpenEnv v0.2.2
* Concurrency: Enabled (Isolation via Session ID)
* Score Range: (0.01, 0.99)

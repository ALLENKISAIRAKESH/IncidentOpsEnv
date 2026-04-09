"""
IncidentOpsEnv  Baseline Inference Script
============================================
Compliant with OpenEnv Hackathon specifications.

Usage:
    export API_BASE_URL="https://api.openai.com/v1"
    export MODEL_NAME="gpt-4o-mini"
    export HF_TOKEN="hf_..."
    python inference.py --task easy
"""

import os
import sys
import json
import argparse
import textwrap

from openai import OpenAI
from core_env import IncidentOpsEnv
from models import Action, ActionType

# --- OpenEnv Required Environment Variables ---
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN
)

# ---------------------------------------------------------------------------
# Prompt Format
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert Site Reliability Engineer (SRE) responding to a live production incident.
    Your job is to investigate, diagnose, and remediate the incident as efficiently as possible.

    ## Environment rules
    - You act one step at a time. Each step you submit exactly ONE action as JSON.
    - You have a limited step budget. Use it wisely.
    - The environment accepts ONLY valid JSON.

    ## Action schema
    {
      "action_type": "<one of the allowed action types>",
      "target_service": "<service name or null>",
      "target_flag": "<feature flag name or null>",
      "target_queue": "<queue name or null>",
      "severity": "<low|medium|high|critical or null>",
      "hypothesis": "<root cause hypothesis or null>",
      "message_template": "<one of the message templates or null>",
      "team_name": "<team name or null>"
    }

    ActionType values:
      view_alerts, view_logs, check_metrics, check_recent_deploys,
      view_dependency_map, inspect_feature_flags,
      classify_severity, hypothesize_root_cause,
      restart_service, rollback_deploy, scale_service, disable_feature_flag,
      post_status_update, escalate_team, resolve_incident
""")

def observation_to_user_message(obs, last_result: str) -> str:
    lines = [
        f"INCIDENT: {obs.incident_id}",
        f"Budget: {obs.remaining_step_budget}",
        f"Summary: {obs.incident_summary}",
    ]
    if obs.known_alerts:
        lines += [f"Alerts: {[a.message for a in obs.known_alerts]}"]
    if obs.retrieved_logs:
        lines += [f"Logs: {list(obs.retrieved_logs.keys())}"]
    if obs.retrieved_metrics:
        lines += [f"Metrics: {list(obs.retrieved_metrics.keys())}"]
    
    if last_result:
        lines += [f"Last action result: {last_result}"]
        
    lines.append("Respond with JSON action:")
    return "\n".join(lines)

def parse_action(text: str) -> Action:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        stripped = inner.strip()

    data = json.loads(stripped)
    allowed = {
        "action_type", "target_service", "target_flag", "target_queue",
        "severity", "hypothesis", "message_template", "team_name"
    }
    cleaned = {k: v for k, v in data.items() if k in allowed and v is not None}
    return Action(**cleaned)

# ---------------------------------------------------------------------------
# Core Inference loop
# ---------------------------------------------------------------------------

def run_episode(task: str):
    env = IncidentOpsEnv(task=task)
    obs = env.reset()

    # Hackathon stdout specification: exactly 3 line types format.
    benchmark_env = "incident-ops-env"
    print(f"[START] task={task} env={benchmark_env} model={MODEL_NAME}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    last_result = ""
    step = 0
    rewards_history = []
    
    done = False
    
    while not done:
        step += 1
        user_msg = observation_to_user_message(obs, last_result)
        messages.append({"role": "user", "content": user_msg})

        error_msg = "null"
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.2,
                max_tokens=256,
            )
            raw_reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": raw_reply})
            action = parse_action(raw_reply)
        except Exception as e:
            # Construct a safe do-nothing fallback to prevent crash and continue loop
            action = Action(action_type=ActionType.VIEW_ALERTS)
            error_msg = str(e).replace('\n', ' ')

        action_str = env._action_key(action).replace('\n', '')

        # Environment step
        obs = env.step(action)
        reward = float(obs.reward)
        done = obs.done
        last_result = obs.last_action_result

        rewards_history.append(f"{reward:.2f}")

        # Hackathon formatting exactly for stdout prints step
        done_str = "true" if done else "false"
        print(f"[STEP] step={step} action={action_str} reward={reward:.2f} done={done_str} error={error_msg}")

    # Success criteria logic - determined by final resolution validation state.
    final_score = float(obs.final_score) if obs.done else 0.0
    success_str = "true" if obs.is_resolved and final_score > 0.0 else "false"
    rewards_joined = ",".join(rewards_history)
    print(f"[END] success={success_str} steps={step} score={final_score:.2f} rewards={rewards_joined}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="easy")
    args = parser.parse_args()
    
    run_episode(args.task)

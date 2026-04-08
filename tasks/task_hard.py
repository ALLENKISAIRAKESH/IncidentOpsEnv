"""
Task 3 (Hard): Multi-Signal Incident with Risky Trade-offs
Narrative: After a new feature flag rollout (auth-v2), the system shows auth
           token errors, elevated checkout latency, delayed order jobs, and
           fraud-detector anomalies. Most signals are correlated but only one
           is causal. The agent must:
             - Gather multi-source evidence
             - Identify that the feature-flag rollout (auth-v2) is the root cause
             - Disable the feature flag (NOT restart auth-service)
             - Escalate to security-team (required)
             - Post a status update before resolving

Correct path:
  view_alerts -> inspect_feature_flags -> view_logs(auth-service) ->
  check_recent_deploys -> check_metrics(auth-service) ->
  classify_severity(critical) ->
  hypothesize_root_cause(feature_flag_misconfiguration) ->
  escalate_team(security-team) ->
  disable_feature_flag(auth-v2) ->
  post_status_update(mitigation_applied) ->
  resolve_incident
"""

from models import (
    ActionType, AlertItem, DeployRecord, EvidenceMap, FeatureFlagState,
    FeatureFlagName, InternalState, LogEntry, MetricSnapshot, Observation,
    RootCauseHypothesis, ScoreComponents, ServiceName, SeverityLevel, TeamName,
)

INCIDENT_ID = "INC-003"
TASK_NAME = "multi_signal_feature_flag"
MAX_STEPS = 12

# ─── Static evidence data ────────────────────────────────────────────────────

ALERTS = [
    AlertItem(
        alert_id="ALT-9800",
        service="auth-service",
        severity="critical",
        message="Auth service token validation failure rate > 28% — sessions rejecting valid tokens",
        triggered_at="2024-04-01T09:05:00Z",
    ),
    AlertItem(
        alert_id="ALT-9801",
        service="checkout-service",
        severity="high",
        message="Checkout latency p99 > 8s — users timing out at payment confirmation step",
        triggered_at="2024-04-01T09:06:30Z",
    ),
    AlertItem(
        alert_id="ALT-9802",
        service="order-worker",
        severity="medium",
        message="Order processing job delays — queue depth at 3x normal level",
        triggered_at="2024-04-01T09:07:00Z",
    ),
    AlertItem(
        alert_id="ALT-9803",
        service="fraud-detector",
        severity="medium",
        message="Fraud detection anomaly score elevated — unusual transaction pattern detected",
        triggered_at="2024-04-01T09:08:00Z",
    ),
    AlertItem(
        alert_id="ALT-9804",
        service="cache-layer",
        severity="low",
        message="Cache eviction rate slightly elevated — within tolerated bounds",
        triggered_at="2024-04-01T09:04:00Z",
    ),
]

LOGS: dict = {
    "auth-service": [
        LogEntry(
            timestamp="2024-04-01T09:03:10Z",
            level="INFO",
            service="auth-service",
            message="Feature flag 'auth-v2' enabled at 09:00 UTC — rolling out to 100% traffic",
        ),
        LogEntry(
            timestamp="2024-04-01T09:03:45Z",
            level="ERROR",
            service="auth-service",
            message="JWT signing key mismatch — auth-v2 uses RS256 but clients expect HS256",
        ),
        LogEntry(
            timestamp="2024-04-01T09:04:00Z",
            level="ERROR",
            service="auth-service",
            message="Token validation failed for 1,240 requests in last 60s [auth-v2 path]",
        ),
        LogEntry(
            timestamp="2024-04-01T09:04:30Z",
            level="ERROR",
            service="auth-service",
            message="Sessions for authenticated users being invalidated — auth-v2 incompatible token format",
        ),
        LogEntry(
            timestamp="2024-04-01T09:05:00Z",
            level="WARN",
            service="auth-service",
            message="Downstream services receiving 401 Unauthorized — all authenticated endpoints affected",
        ),
    ],
    "checkout-service": [
        LogEntry(
            timestamp="2024-04-01T09:05:20Z",
            level="WARN",
            service="checkout-service",
            message="401 Unauthorized from auth-service — checkout abandoning session for user_id=34812",
        ),
        LogEntry(
            timestamp="2024-04-01T09:05:40Z",
            level="ERROR",
            service="checkout-service",
            message="Session validation timeout — auth round-trips taking >7s due to retry logic",
        ),
    ],
    "fraud-detector": [
        LogEntry(
            timestamp="2024-04-01T09:06:00Z",
            level="WARN",
            service="fraud-detector",
            message="Unusual burst of anonymous/unauthenticated transactions flagged as anomalous",
        ),
        LogEntry(
            timestamp="2024-04-01T09:06:30Z",
            level="INFO",
            service="fraud-detector",
            message="Anomaly likely an artifact of auth failures generating unauthenticated request spikes",
        ),
    ],
    "order-worker": [
        LogEntry(
            timestamp="2024-04-01T09:07:00Z",
            level="WARN",
            service="order-worker",
            message="Order confirmation events reduced — fewer orders completing due to checkout auth failures",
        ),
    ],
    "cache-layer": [
        LogEntry(
            timestamp="2024-04-01T09:04:10Z",
            level="INFO",
            service="cache-layer",
            message="Cache eviction slightly elevated — routine pattern, no action needed",
        ),
    ],
}

METRICS: dict = {
    "auth-service": MetricSnapshot(
        service="auth-service",
        error_rate_pct=28.3,
        latency_p99_ms=6800.0,
        requests_per_sec=2300.0,
        cpu_usage_pct=71.0,
        memory_usage_pct=65.0,
    ),
    "checkout-service": MetricSnapshot(
        service="checkout-service",
        error_rate_pct=19.7,
        latency_p99_ms=8200.0,
        requests_per_sec=540.0,
        cpu_usage_pct=44.0,
        memory_usage_pct=52.0,
    ),
    "order-worker": MetricSnapshot(
        service="order-worker",
        error_rate_pct=0.4,
        latency_p99_ms=310.0,
        requests_per_sec=62.0,
        cpu_usage_pct=28.0,
        memory_usage_pct=41.0,
    ),
    "fraud-detector": MetricSnapshot(
        service="fraud-detector",
        error_rate_pct=0.2,
        latency_p99_ms=95.0,
        requests_per_sec=140.0,
        cpu_usage_pct=19.0,
        memory_usage_pct=33.0,
    ),
    "cache-layer": MetricSnapshot(
        service="cache-layer",
        error_rate_pct=0.0,
        latency_p99_ms=22.0,
        requests_per_sec=3100.0,
        cpu_usage_pct=25.0,
        memory_usage_pct=44.0,
    ),
}

DEPLOYS: list = [
    DeployRecord(
        deploy_id="DPLY-610",
        service="auth-service",
        version="v4.2.0",
        deployed_at="2024-04-01T08:45:00Z",
        deployed_by="ci-bot",
        status="success",
        notes="Infrastructure prep for auth-v2 feature flag — no functional change without flag",
    ),
    DeployRecord(
        deploy_id="DPLY-609",
        service="fraud-detector",
        version="v2.1.5",
        deployed_at="2024-03-31T17:00:00Z",
        deployed_by="engineer-mia",
        status="success",
        notes="Model weight update — improved precision on international transactions",
    ),
]

FEATURE_FLAGS: list = [
    FeatureFlagState(
        flag_name=FeatureFlagName.AUTH_V2,
        enabled=True,
        rollout_pct=100,
        last_modified="2024-04-01T09:00:00Z",
    ),
    FeatureFlagState(
        flag_name=FeatureFlagName.FRAUD_DETECTION_V3,
        enabled=False,
        rollout_pct=0,
        last_modified="2024-03-28T10:00:00Z",
    ),
    FeatureFlagState(
        flag_name=FeatureFlagName.NEW_CHECKOUT_FLOW,
        enabled=False,
        rollout_pct=0,
        last_modified="2024-03-15T08:00:00Z",
    ),
]

DEPENDENCY_MAP: dict = {
    "checkout-service": ["auth-service", "payment-api", "cache-layer"],
    "auth-service": [],
    "order-worker": ["database", "auth-service"],
    "fraud-detector": ["auth-service"],
    "cache-layer": [],
    "payment-api": ["database", "auth-service"],
}


def get_hard_task() -> tuple[Observation, object]:
    """Return initial (observation, internal_state) for the hard task."""

    initial_obs = Observation(
        incident_id=INCIDENT_ID,
        task_name=TASK_NAME,
        incident_summary=(
            "CRITICAL INCIDENT — Multiple services degraded simultaneously. "
            "Auth token failures, elevated checkout latency, order job delays, "
            "and fraud detection anomalies all firing at once. "
            "A feature flag was recently enabled. Determine root cause and respond safely."
        ),
        current_status="open",
        affected_services=["auth-service", "checkout-service", "order-worker", "fraud-detector"],
        severity_guessable_signals=(
            "Auth failures cascade into checkout, jobs, and fraud systems. "
            "Auth is a core dependency. Feature flag 'auth-v2' was enabled at ~09:00 UTC — "
            "same time as incident onset. Security implications possible."
        ),
        remaining_step_budget=MAX_STEPS,
        allowed_actions=_allowed_actions(),
    )

    internal = InternalState(
        incident_id=INCIDENT_ID,
        task_name=TASK_NAME,
        max_steps=MAX_STEPS,
        root_cause=RootCauseHypothesis.FEATURE_FLAG_MISCONFIGURATION,
        correct_mitigation=ActionType.DISABLE_FEATURE_FLAG,
        correct_mitigation_target=FeatureFlagName.AUTH_V2,
        correct_severity=SeverityLevel.CRITICAL,
        requires_escalation=True,
        required_escalation_team=TeamName.SECURITY,
        requires_communication=True,
        score_components=ScoreComponents(safety_score=1.0),
    )

    return initial_obs, internal


def _allowed_actions() -> list:
    return [
        "view_alerts",
        "view_logs {service}",
        "check_metrics {service}",
        "check_recent_deploys",
        "view_dependency_map",
        "inspect_feature_flags",
        "classify_severity {low|medium|high|critical}",
        "hypothesize_root_cause {cause}",
        "restart_service {service}",
        "rollback_deploy {service}",
        "scale_service {service}",
        "disable_feature_flag {flag}",
        "post_status_update {template}",
        "escalate_team {team}",
        "resolve_incident",
    ]


def get_alerts() -> list:
    return ALERTS

def get_logs(service: str) -> list:
    return LOGS.get(service, [])

def get_metrics(service: str):
    return METRICS.get(service)

def get_deploys() -> list:
    return DEPLOYS

def get_feature_flags() -> list:
    return FEATURE_FLAGS

def get_dependency_map() -> dict:
    return DEPENDENCY_MAP

# Grader metadata
RELEVANT_LOG_SERVICES = {"auth-service", "checkout-service", "fraud-detector"}
HARMFUL_MITIGATIONS = {
    # Restarting auth without disabling flag won't fix the token format mismatch
    (ActionType.RESTART_SERVICE, "auth-service"),
    # Rolling back the deploy won't help — the deploy was a no-op without the flag
    (ActionType.ROLLBACK_DEPLOY, "auth-service"),
    # Disabling fraud-detector is dangerous and incorrect
    (ActionType.DISABLE_FEATURE_FLAG, FeatureFlagName.FRAUD_DETECTION_V3),
    # Scaling auth won't fix a config mismatch
    (ActionType.SCALE_SERVICE, "auth-service"),
}

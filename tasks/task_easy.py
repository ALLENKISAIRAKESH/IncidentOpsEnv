"""
Task 1 (Easy): Database Pool Exhaustion in Payment API
Narrative: Users experience payment failures. Logs clearly indicate DB connection timeouts.
Correct path: view_alerts -> view_logs(payment-api) -> classify_severity(high) ->
              hypothesize_root_cause(db_connection_pool_exhaustion) ->
              restart_service(payment-api) -> post_status_update -> resolve_incident
"""

from models import (
    ActionType, AlertItem, DeployRecord, EvidenceMap, FeatureFlagState,
    FeatureFlagName, InternalState, LogEntry, MetricSnapshot, Observation,
    RootCauseHypothesis, ScoreComponents, ServiceName, SeverityLevel, TeamName,
)


INCIDENT_ID = "INC-001"
TASK_NAME = "database_pool_exhaustion"
MAX_STEPS = 7

# ─── Static evidence data ────────────────────────────────────────────────────

ALERTS = [
    AlertItem(
        alert_id="ALT-8821",
        service="payment-api",
        severity="high",
        message="Payment API error rate > 35% — transaction failures detected",
        triggered_at="2024-03-15T10:02:00Z",
    ),
    AlertItem(
        alert_id="ALT-8822",
        service="database",
        severity="high",
        message="DB connection pool utilisation at 100% — new connections being refused",
        triggered_at="2024-03-15T10:01:45Z",
    ),
]

LOGS: dict = {
    "payment-api": [
        LogEntry(
            timestamp="2024-03-15T10:01:50Z",
            level="ERROR",
            service="payment-api",
            message="Unable to acquire DB connection from pool: timeout after 30s",
        ),
        LogEntry(
            timestamp="2024-03-15T10:01:52Z",
            level="ERROR",
            service="payment-api",
            message="Transaction failed for user_id=9912: DB connection pool exhausted",
        ),
        LogEntry(
            timestamp="2024-03-15T10:01:55Z",
            level="ERROR",
            service="payment-api",
            message="Retry #3 failed — HikariPool connection unavailable",
        ),
        LogEntry(
            timestamp="2024-03-15T10:02:00Z",
            level="WARN",
            service="payment-api",
            message="Circuit breaker OPEN — downstream DB calls blocked",
        ),
    ],
    "database": [
        LogEntry(
            timestamp="2024-03-15T10:00:30Z",
            level="WARN",
            service="database",
            message="Active connections approaching pool limit (49/50)",
        ),
        LogEntry(
            timestamp="2024-03-15T10:01:00Z",
            level="ERROR",
            service="database",
            message="Pool limit reached (50/50). New connection requests queued.",
        ),
        LogEntry(
            timestamp="2024-03-15T10:01:48Z",
            level="ERROR",
            service="database",
            message="Connection request timed out after 30s. Pool still saturated.",
        ),
    ],
}

METRICS: dict = {
    "payment-api": MetricSnapshot(
        service="payment-api",
        error_rate_pct=38.4,
        latency_p99_ms=31200.0,
        requests_per_sec=420.0,
        cpu_usage_pct=52.0,
        memory_usage_pct=61.0,
    ),
    "database": MetricSnapshot(
        service="database",
        error_rate_pct=2.1,
        latency_p99_ms=5800.0,
        requests_per_sec=390.0,
        cpu_usage_pct=88.0,
        memory_usage_pct=74.0,
    ),
}

DEPLOYS: list = [
    DeployRecord(
        deploy_id="DPLY-441",
        service="payment-api",
        version="v2.4.1",
        deployed_at="2024-03-14T18:00:00Z",
        deployed_by="ci-bot",
        status="success",
        notes="Minor logging improvements — no schema changes",
    ),
]

FEATURE_FLAGS: list = [
    FeatureFlagState(
        flag_name=FeatureFlagName.PAYMENT_RETRY_LOGIC,
        enabled=True,
        rollout_pct=100,
        last_modified="2024-03-10T12:00:00Z",
    ),
]

DEPENDENCY_MAP: dict = {
    "payment-api": ["database", "fraud-detector"],
    "database": [],
    "fraud-detector": [],
}

# Noise logs (for a non-critical service) — low noise in easy task
NOISE_LOGS: dict = {
    "auth-service": [
        LogEntry(
            timestamp="2024-03-15T10:00:00Z",
            level="INFO",
            service="auth-service",
            message="Auth token refresh completed successfully for 142 sessions",
        ),
    ],
}


# ─── Task factory ────────────────────────────────────────────────────────────

def get_easy_task() -> tuple[Observation, InternalState]:
    """Return the initial (observation, internal_state) for the easy task."""

    initial_obs = Observation(
        incident_id=INCIDENT_ID,
        task_name=TASK_NAME,
        incident_summary=(
            "INCIDENT ACTIVE — Payment service is experiencing elevated error rates. "
            "Users are unable to complete checkout transactions. "
            "Customer support is receiving reports. Investigate immediately."
        ),
        current_status="open",
        affected_services=["payment-api"],
        severity_guessable_signals=(
            "Payment errors are user-facing. Checkout is broken for a significant "
            "fraction of users. Business impact is HIGH."
        ),
        remaining_step_budget=MAX_STEPS,
        allowed_actions=_allowed_actions(),
    )

    internal = InternalState(
        incident_id=INCIDENT_ID,
        task_name=TASK_NAME,
        max_steps=MAX_STEPS,
        root_cause=RootCauseHypothesis.DB_CONNECTION_POOL_EXHAUSTION,
        correct_mitigation=ActionType.RESTART_SERVICE,
        correct_mitigation_target=ServiceName.PAYMENT_API,
        correct_severity=SeverityLevel.HIGH,
        requires_escalation=False,
        requires_communication=True,
        score_components=ScoreComponents(safety_score=1.0),
    )

    return initial_obs, internal


def _allowed_actions() -> list:
    return [
        "view_alerts",
        "view_logs {service}  — e.g. view_logs payment-api",
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


# ─── Evidence accessors (called by environment) ──────────────────────────────

def get_alerts() -> list:
    return ALERTS

def get_logs(service: str) -> list:
    combined = {**LOGS, **NOISE_LOGS}
    return combined.get(service, [])

def get_metrics(service: str) -> MetricSnapshot | None:
    return METRICS.get(service)

def get_deploys() -> list:
    return DEPLOYS

def get_feature_flags() -> list:
    return FEATURE_FLAGS

def get_dependency_map() -> dict:
    return DEPENDENCY_MAP

# Services relevant to this incident — used by grader
RELEVANT_LOG_SERVICES = {"payment-api", "database"}
HARMFUL_MITIGATIONS = {
    # rolling back a stable deploy when there's no deploy issue is harmful
    (ActionType.ROLLBACK_DEPLOY, "payment-api"),
    (ActionType.DISABLE_FEATURE_FLAG, FeatureFlagName.PAYMENT_RETRY_LOGIC),
}

"""
Task 2 (Medium): Checkout Failure from Faulty Deploy
Narrative: Checkout failures spike after a recent deployment.
           Alerts point to cache latency (red herring), but the true
           issue is a deployment regression in checkout-service.
           Agent must avoid the misleading signal and rollback the deploy.

Correct path:
  view_alerts -> check_recent_deploys -> view_logs(checkout-service) ->
  classify_severity(high) -> hypothesize_root_cause(bad_deploy_regression) ->
  rollback_deploy(checkout-service) -> post_status_update -> resolve_incident
"""

from models import (
    ActionType, AlertItem, DeployRecord, EvidenceMap, FeatureFlagState,
    FeatureFlagName, InternalState, LogEntry, MetricSnapshot, Observation,
    RootCauseHypothesis, ScoreComponents, ServiceName, SeverityLevel, TeamName,
)
from .utils import generate_noise_logs

INCIDENT_ID = "INC-002"
TASK_NAME = "checkout_faulty_deploy"
MAX_STEPS = 9

#  Static evidence data 

ALERTS = [
    AlertItem(
        alert_id="ALT-9100",
        service="checkout-service",
        severity="high",
        message="Checkout service error rate spiked to 42%  orders not completing",
        triggered_at="2024-03-20T14:15:00Z",
    ),
    AlertItem(
        alert_id="ALT-9101",
        service="cache-layer",
        severity="medium",
        message="Cache hit ratio dropped to 61%  elevated cache miss latency detected",
        triggered_at="2024-03-20T14:14:30Z",
    ),
    AlertItem(
        alert_id="ALT-9102",
        service="order-worker",
        severity="low",
        message="Order worker queue depth increased  downstream of checkout failures",
        triggered_at="2024-03-20T14:16:00Z",
    ),
]

LOGS: dict = {
    "checkout-service": [
        LogEntry(
            timestamp="2024-03-20T14:13:50Z",
            level="ERROR",
            service="checkout-service",
            message="NullPointerException in CheckoutController.applyPromoCode() [v3.1.0]",
        ),
        LogEntry(
            timestamp="2024-03-20T14:13:55Z",
            level="ERROR",
            service="checkout-service",
            message="Order submission failed  stack trace: PromoCodeService.validate() returned null",
        ),
        LogEntry(
            timestamp="2024-03-20T14:14:02Z",
            level="ERROR",
            service="checkout-service",
            message="500 Internal Server Error for POST /checkout/submit  promo validation crash",
        ),
        LogEntry(
            timestamp="2024-03-20T14:14:10Z",
            level="WARN",
            service="checkout-service",
            message="v3.1.0 deployed 14:10 UTC  errors began immediately after. Previous version: v3.0.8",
        ),
    ],
    "cache-layer": [
        LogEntry(
            timestamp="2024-03-20T14:13:00Z",
            level="WARN",
            service="cache-layer",
            message="Cache eviction triggered  TTL adjustment in progress (routine maintenance)",
        ),
        LogEntry(
            timestamp="2024-03-20T14:14:00Z",
            level="INFO",
            service="cache-layer",
            message="Cache miss rate elevated but within acceptable degraded threshold",
        ),
    ],
    "order-worker": [
        LogEntry(
            timestamp="2024-03-20T14:15:30Z",
            level="WARN",
            service="order-worker",
            message="Queue depth rising  upstream checkout submission failures causing reduced inflow",
        ),
    ],
}

METRICS: dict = {
    "checkout-service": MetricSnapshot(
        service="checkout-service",
        error_rate_pct=42.3,
        latency_p99_ms=4200.0,
        requests_per_sec=610.0,
        cpu_usage_pct=41.0,
        memory_usage_pct=55.0,
    ),
    "cache-layer": MetricSnapshot(
        service="cache-layer",
        error_rate_pct=0.1,
        latency_p99_ms=280.0,
        requests_per_sec=1800.0,
        cpu_usage_pct=33.0,
        memory_usage_pct=48.0,
    ),
    "order-worker": MetricSnapshot(
        service="order-worker",
        error_rate_pct=0.3,
        latency_p99_ms=120.0,
        requests_per_sec=85.0,
        cpu_usage_pct=22.0,
        memory_usage_pct=38.0,
    ),
}

DEPLOYS: list = [
    DeployRecord(
        deploy_id="DPLY-550",
        service="checkout-service",
        version="v3.1.0",
        deployed_at="2024-03-20T14:10:00Z",
        deployed_by="engineer-prakash",
        status="success",
        notes="Added promo code validation refactor  untested edge case in null handling",
    ),
    DeployRecord(
        deploy_id="DPLY-549",
        service="cache-layer",
        version="v1.8.2",
        deployed_at="2024-03-20T12:30:00Z",
        deployed_by="ci-bot",
        status="success",
        notes="Routine TTL config update",
    ),
]

FEATURE_FLAGS: list = [
    FeatureFlagState(
        flag_name=FeatureFlagName.NEW_CHECKOUT_FLOW,
        enabled=False,
        rollout_pct=0,
        last_modified="2024-03-18T09:00:00Z",
    ),
]

DEPENDENCY_MAP: dict = {
    "checkout-service": ["cache-layer", "order-worker", "payment-api"],
    "cache-layer": [],
    "order-worker": ["database"],
    "payment-api": ["database"],
}

# Noise logs
NOISE_LOGS: dict = {
    "auth-service": generate_noise_logs("auth-service"),
    "fraud-detector": generate_noise_logs("fraud-detector"),
}


def get_medium_task() -> tuple[Observation, InternalState]:
    """Return initial (observation, internal_state) for the medium task."""

    initial_obs = Observation(
        incident_id=INCIDENT_ID,
        task_name=TASK_NAME,
        incident_summary=(
            "INCIDENT ACTIVE  Checkout service showing >40% error rate. "
            "Customers unable to complete purchases. Cache latency alerts also firing. "
            "Multiple signals in play. Identify the root cause and respond."
        ),
        current_status="open",
        affected_services=["checkout-service"],
        severity_guessable_signals=(
            "Checkout failures are directly customer-facing. Revenue impact is occurring now. "
            "Cache latency is also reported  determine if this is related or a red herring."
        ),
        remaining_step_budget=MAX_STEPS,
        allowed_actions=_allowed_actions(),
    )

    internal = InternalState(
        incident_id=INCIDENT_ID,
        task_name=TASK_NAME,
        max_steps=MAX_STEPS,
        root_cause=RootCauseHypothesis.BAD_DEPLOY_REGRESSION,
        correct_mitigation=ActionType.ROLLBACK_DEPLOY,
        correct_mitigation_target=ServiceName.CHECKOUT_SERVICE,
        correct_severity=SeverityLevel.HIGH,
        requires_escalation=False,
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
    combined = {**LOGS, **NOISE_LOGS}
    return combined.get(service, [])

def get_metrics(service: str):
    return METRICS.get(service)

def get_deploys() -> list:
    return DEPLOYS

def get_feature_flags() -> list:
    return FEATURE_FLAGS

def get_dependency_map() -> dict:
    return DEPENDENCY_MAP

# Grader metadata
RELEVANT_LOG_SERVICES = {"checkout-service", "cache-layer"}
HARMFUL_MITIGATIONS = {
    # Restarting cache is irrelevant and disruptive
    (ActionType.RESTART_SERVICE, ServiceName.CACHE_LAYER),
    # Rolling back cache deploy is incorrect  that deploy is not the cause
    (ActionType.ROLLBACK_DEPLOY, ServiceName.CACHE_LAYER),
    # Incorrect root cause that leads to wrong fix
    (ActionType.RESTART_SERVICE, ServiceName.CHECKOUT_SERVICE),  # restart  rollback for regression
}

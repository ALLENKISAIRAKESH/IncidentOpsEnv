"""
IncidentOpsEnv - Typed Pydantic Models
Defines all typed data structures for observation, action, reward, and internal state.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    # Investigation actions
    VIEW_ALERTS = "view_alerts"
    VIEW_LOGS = "view_logs"
    CHECK_METRICS = "check_metrics"
    CHECK_RECENT_DEPLOYS = "check_recent_deploys"
    VIEW_DEPENDENCY_MAP = "view_dependency_map"
    INSPECT_FEATURE_FLAGS = "inspect_feature_flags"

    # Reasoning actions
    CLASSIFY_SEVERITY = "classify_severity"
    HYPOTHESIZE_ROOT_CAUSE = "hypothesize_root_cause"

    # Remediation actions
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOY = "rollback_deploy"
    SCALE_SERVICE = "scale_service"
    DISABLE_FEATURE_FLAG = "disable_feature_flag"
    CLEAR_QUEUE = "clear_queue"

    # Communication actions
    POST_STATUS_UPDATE = "post_status_update"
    ESCALATE_TEAM = "escalate_team"

    # Completion action
    RESOLVE_INCIDENT = "resolve_incident"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceName(str, Enum):
    AUTH_SERVICE = "auth-service"
    PAYMENT_API = "payment-api"
    CHECKOUT_SERVICE = "checkout-service"
    ORDER_WORKER = "order-worker"
    CACHE_LAYER = "cache-layer"
    DATABASE = "database"
    FEATURE_FLAG_SERVICE = "feature-flag-service"
    FRAUD_DETECTOR = "fraud-detector"


class TeamName(str, Enum):
    PLATFORM = "platform-team"
    SECURITY = "security-team"
    DATABASE = "database-team"
    PAYMENTS = "payments-team"
    SRE = "sre-team"


class RootCauseHypothesis(str, Enum):
    DB_CONNECTION_POOL_EXHAUSTION = "db_connection_pool_exhaustion"
    BAD_DEPLOY_REGRESSION = "bad_deploy_regression"
    FEATURE_FLAG_MISCONFIGURATION = "feature_flag_misconfiguration"
    CACHE_INVALIDATION_FAILURE = "cache_invalidation_failure"
    MEMORY_LEAK = "memory_leak"
    NETWORK_PARTITION = "network_partition"
    THIRD_PARTY_API_OUTAGE = "third_party_api_outage"
    AUTH_TOKEN_EXPIRY = "auth_token_expiry"
    QUEUE_BACKPRESSURE = "queue_backpressure"
    RESOURCE_STARVATION = "resource_starvation"


class MessageTemplate(str, Enum):
    INVESTIGATING = "We are currently investigating the incident and will provide updates."
    ROOT_CAUSE_IDENTIFIED = "Root cause has been identified. Remediation is in progress."
    MITIGATION_APPLIED = "Mitigation has been applied. We are monitoring for recovery."
    RESOLVED = "The incident has been resolved. Services are back to normal."
    ESCALATED = "The incident has been escalated to the appropriate team."
    MONITORING = "We are monitoring the situation. No action required at this time."


class QueueName(str, Enum):
    NOTIFICATION_QUEUE = "notification-queue"
    ORDER_PROCESSING_QUEUE = "order-processing-queue"
    FRAUD_CHECKS_QUEUE = "fraud-checks-queue"


class FeatureFlagName(str, Enum):
    NEW_CHECKOUT_FLOW = "new-checkout-flow"
    AUTH_V2 = "auth-v2"
    FRAUD_DETECTION_V3 = "fraud-detection-v3"
    PAYMENT_RETRY_LOGIC = "payment-retry-logic"
    ASYNC_NOTIFICATIONS = "async-notifications"


# ---------------------------------------------------------------------------
# Action Model
# ---------------------------------------------------------------------------

class Action(BaseModel):
    """Strongly typed action submitted by the agent."""

    action_type: ActionType = Field(..., description="The type of action to execute.")
    target_service: Optional[ServiceName] = Field(
        None, description="Target service for service-specific actions."
    )
    target_flag: Optional[FeatureFlagName] = Field(
        None, description="Target feature flag name for flag-related actions."
    )
    target_queue: Optional[QueueName] = Field(
        None, description="Target queue for queue-related actions."
    )
    severity: Optional[SeverityLevel] = Field(
        None, description="Severity level for classify_severity action."
    )
    hypothesis: Optional[RootCauseHypothesis] = Field(
        None, description="Root cause hypothesis for hypothesize_root_cause action."
    )
    message_template: Optional[MessageTemplate] = Field(
        None, description="Message template for post_status_update action."
    )
    team_name: Optional[TeamName] = Field(
        None, description="Team to escalate to for escalate_team action."
    )

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# Observation Model
# ---------------------------------------------------------------------------

class AlertItem(BaseModel):
    alert_id: str
    service: str
    severity: str
    message: str
    triggered_at: str


class LogEntry(BaseModel):
    timestamp: str
    level: str
    service: str
    message: str


class MetricSnapshot(BaseModel):
    service: str
    error_rate_pct: float
    latency_p99_ms: float
    requests_per_sec: float
    cpu_usage_pct: float
    memory_usage_pct: float


class DeployRecord(BaseModel):
    deploy_id: str
    service: str
    version: str
    deployed_at: str
    deployed_by: str
    status: str
    notes: Optional[str] = None


class FeatureFlagState(BaseModel):
    flag_name: str
    enabled: bool
    rollout_pct: int
    last_modified: str


class Observation(BaseModel):
    """All externally visible information returned after each step."""

    incident_id: str
    task_name: str
    incident_summary: str
    current_status: str
    affected_services: List[str]
    severity_guessable_signals: str

    # Incrementally revealed evidence
    known_alerts: List[AlertItem] = Field(default_factory=list)
    retrieved_logs: Dict[str, List[LogEntry]] = Field(default_factory=dict)
    retrieved_metrics: Dict[str, MetricSnapshot] = Field(default_factory=dict)
    recent_deploys: List[DeployRecord] = Field(default_factory=list)
    feature_flag_states: List[FeatureFlagState] = Field(default_factory=list)
    dependency_map: Optional[Dict[str, List[str]]] = None

    # Reasoning state
    classified_severity: Optional[str] = None
    hypothesized_root_cause: Optional[str] = None
    posted_status_updates: List[str] = Field(default_factory=list)
    escalated_teams: List[str] = Field(default_factory=list)

    # Action tracking
    action_history: List[str] = Field(default_factory=list)
    last_action_result: str = ""
    remaining_step_budget: int = 12
    is_resolved: bool = Field(default=False, description="Whether the incident has been successfully resolved.")
    reward: float = Field(default=0.0, description="Step isolated reward float representing incremental logic outcome.")
    final_score: float = Field(default=0.0, description="The final 0.0-1.0 score assigned by the grader at the end of the episode.")
    done: bool = Field(default=False, description="Terminal state indicator.")
    allowed_actions: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reward Model
# ---------------------------------------------------------------------------

class RewardComponents(BaseModel):
    evidence_collection: float = 0.0
    severity_correctness: float = 0.0
    root_cause_correctness: float = 0.0
    mitigation_correctness: float = 0.0
    communication_quality: float = 0.0
    efficiency: float = 0.0
    safety: float = 0.0


class Reward(BaseModel):
    """Reward returned after every step."""

    scalar: float = Field(..., description="Scalar reward for the last action, can be negative.")
    total_cumulative_score: float = Field(
        0.0, description="Cumulative score accumulated so far in the episode."
    )
    rationale: str = Field("", description="Human-readable rationale for the reward given.")
    components: Optional[RewardComponents] = None


# ---------------------------------------------------------------------------
# Step Result
# ---------------------------------------------------------------------------

class StepResult(BaseModel):
    """Returned by env.step(action)."""

    observation: Observation
    reward: Reward
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal State Model (richer than observation)
# ---------------------------------------------------------------------------

class EvidenceMap(BaseModel):
    alerts_viewed: bool = False
    logs_viewed: Dict[str, bool] = Field(default_factory=dict)
    metrics_checked: Dict[str, bool] = Field(default_factory=dict)
    deploys_checked: bool = False
    dependency_viewed: bool = False
    flags_inspected: bool = False


class ScoreComponents(BaseModel):
    evidence_score: float = 0.0
    severity_score: float = 0.0
    cause_score: float = 0.0
    mitigation_score: float = 0.0
    communication_score: float = 0.0
    efficiency_score: float = 0.0
    safety_score: float = 1.0  # starts at full, penalized for harm


class InternalState(BaseModel):
    """Complete ground-truth internal state — not exposed to the agent."""

    incident_id: str
    task_name: str
    episode_step: int = 0
    max_steps: int = 12

    # Ground truth
    root_cause: RootCauseHypothesis
    correct_mitigation: ActionType
    correct_mitigation_target: Optional[str] = None
    correct_severity: SeverityLevel
    requires_escalation: bool = False
    required_escalation_team: Optional[TeamName] = None
    requires_communication: bool = True

    # Evidence tracking
    evidence_map: EvidenceMap = Field(default_factory=EvidenceMap)

    # Agent reasoning tracking
    severity_classified: Optional[str] = None
    severity_classified_correctly: bool = False
    hypothesis_submitted: Optional[str] = None
    hypothesis_correct: bool = False
    mitigation_applied: Optional[str] = None
    mitigation_correct: bool = False
    harmful_mitigation_applied: bool = False
    communication_posted: bool = False
    escalation_done: bool = False
    escalation_correct: bool = False
    resolved: bool = False
    premature_resolved: bool = False

    # Spam / penalty tracking
    spam_counter: int = 0
    repeated_actions: Dict[str, int] = Field(default_factory=dict)
    penalties_accumulated: float = 0.0

    # Score tracking
    score_components: ScoreComponents = Field(default_factory=ScoreComponents)
    cumulative_reward: float = 0.0

    class Config:
        use_enum_values = True

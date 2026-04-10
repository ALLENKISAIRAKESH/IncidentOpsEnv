import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_env import IncidentOpsEnv
from models import Action, ActionType, ServiceName, RootCauseHypothesis, FeatureFlagName, TeamName, SeverityLevel

def test_easy():
    print("--- Testing EASY task ---")
    env = IncidentOpsEnv(task_id="easy")
    env.reset()
    
    actions = [
        Action(action_type=ActionType.VIEW_ALERTS),
        Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.PAYMENT_API),
        Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.DB_CONNECTION_POOL_EXHAUSTION),
        Action(action_type=ActionType.RESTART_SERVICE, target_service=ServiceName.DATABASE),
        Action(action_type=ActionType.RESOLVE_INCIDENT)
    ]
    
    score = 0
    for a in actions:
        obs = env.step(a)
        if obs.done:
            score = obs.final_score
            
    print(f"EASY Score: {score}")
    return 0 < score < 1

def test_medium():
    print("--- Testing MEDIUM task ---")
    env = IncidentOpsEnv(task_id="medium")
    env.reset()
    
    actions = [
        Action(action_type=ActionType.VIEW_ALERTS),
        Action(action_type=ActionType.CHECK_RECENT_DEPLOYS),
        Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.CHECKOUT_SERVICE),
        Action(action_type=ActionType.HYPOTHESIZE_ROOT_CAUSE, hypothesis=RootCauseHypothesis.BAD_DEPLOY_REGRESSION),
        Action(action_type=ActionType.ROLLBACK_DEPLOY, target_service=ServiceName.CHECKOUT_SERVICE),
        Action(action_type=ActionType.RESOLVE_INCIDENT)
    ]
    
    score = 0
    for a in actions:
        obs = env.step(a)
        if obs.done:
            score = obs.final_score
            
    print(f"MEDIUM Score: {score}")
    return 0 < score < 1

def test_hard():
    print("--- Testing HARD task ---")
    env = IncidentOpsEnv(task_id="hard")
    env.reset()
    
    actions = [
        Action(action_type=ActionType.VIEW_ALERTS),
        Action(action_type=ActionType.INSPECT_FEATURE_FLAGS),
        Action(action_type=ActionType.VIEW_LOGS, target_service=ServiceName.AUTH_SERVICE),
        Action(action_type=ActionType.ESCALATE_TEAM, team_name=TeamName.SECURITY),
        Action(action_type=ActionType.DISABLE_FEATURE_FLAG, target_flag=FeatureFlagName.AUTH_V2),
        Action(action_type=ActionType.RESOLVE_INCIDENT)
    ]
    
    score = 0
    for a in actions:
        obs = env.step(a)
        if obs.done:
            score = obs.final_score
            
    print(f"HARD Score: {score}")
    return 0 < score < 1

if __name__ == "__main__":
    e = test_easy()
    m = test_medium()
    h = test_hard()
    
    if e and m and h:
        print("\n[PASS] All evaluations passed successfully.")
    else:
        print("\n[FAIL] One or more evaluations failed.")
        sys.exit(1)

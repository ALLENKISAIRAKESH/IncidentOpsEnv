from typing import Dict
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State
from models import Action, Observation

class IncidentClient(EnvClient[Action, Observation, State]):
    """Client for IncidentOpsEnv WebSocket connectivity."""
    def _step_payload(self, action: Action) -> Dict:
        return action.model_dump(mode='json', exclude_none=True)
        
    def _parse_result(self, payload: Dict) -> StepResult[Observation]:
        obs_data = payload.get("observation", {})
        return StepResult(
            observation=Observation(**obs_data),
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False)
        )
        
    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id", "0"),
            step_count=payload.get("step_count", 0)
        )

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server.http_server import create_app
from models import Action, Observation
from core_env import IncidentOpsEnv

from grader import grade_episode

def environment_grader(env: IncidentOpsEnv):
    """Bridge between the environment instance and the rule-based grader."""
    if env.internal_state is None or env.task_module is None:
        return 0.0
    grade = grade_episode(env.internal_state, env.task_module)
    return float(grade.total)

app = create_app(
    IncidentOpsEnv,
    Action,
    Observation,
    env_name="incident-ops-env",
    max_concurrent_envs=10,
    grader=environment_grader,
)

@app.get("/")
async def root():
    return {"message": "IncidentOpsEnv API is live!", "tasks": IncidentOpsEnv.get_task_ids()}

import gradio as gr
try:
    from app import app as gradio_app
    app = gr.mount_gradio_app(app, gradio_app, path="/dashboard")
except Exception as e:
    print("Could not mount visual dashboard:", e)

def main(host: str="0.0.0.0", port: int=8000):
    import uvicorn
    import sys
    # Quick fix for args if needed but defaults work
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()

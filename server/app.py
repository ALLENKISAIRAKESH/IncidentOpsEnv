import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server.http_server import create_app
from models import Action, Observation
from core_env import IncidentOpsEnv

app = create_app(
    IncidentOpsEnv,
    Action,
    Observation,
    env_name="incident-ops-env",
    max_concurrent_envs=10,
)

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

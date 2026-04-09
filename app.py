import gradio as gr
import json
from core_env import IncidentOpsEnv
from models import Action, ActionType, ServiceName, SeverityLevel, RootCauseHypothesis, MessageTemplate, TeamName, FeatureFlagName

def initialize_env(task_name):
    try:
        # Initialize env - ensuring task_id is used consistently
        # The core_env.py uses task_id as the parameter name
        env = IncidentOpsEnv(task_id=task_name)
        obs = env.reset()
        
        # Store initial obs in state
        state = {
            "env": env,
            "history": []
        }
        
        init_msg = f"Environment Initialized: {task_name.upper()}\nIncident ID: {obs.incident_id}\n\nSummary:\n{obs.incident_summary}"
        
        state["history"].append({"role": "assistant", "content": init_msg})
        
        return state, state["history"], obs_to_markdown(obs), gr.update(interactive=True)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"FAILED TO START SIMULATOR:\n{error_trace}")
        return None, [{"role": "assistant", "content": f"Failed to initialize simulator: {str(e)}"}], f"### ❌ Initialization Error\n```\n{str(e)}\n```", gr.update(interactive=False)

def get_topology_map(obs):
    """Generates a visual topology representing service health."""
    services = {
        "checkout-service": "✅",
        "payment-api": "✅",
        "auth-service": "✅",
        "database": "✅",
        "cache-layer": "✅",
        "order-worker": "✅",
        "fraud-detector": "✅"
    }
    
    # Update status based on affected services
    for svc in obs.affected_services:
        if svc in services:
            services[svc] = "❌"
            
    # Also check what has been retrieved
    for svc in obs.retrieved_logs.keys():
        if svc in services and services[svc] != "❌":
            services[svc] = "🔍"

    topology = f"""
    ```mermaid
    graph LR
        User((User)) --> Checkout["{services['checkout-service']} Checkout Service"]
        Checkout --> Payment["{services['payment-api']} Payment API"]
        Checkout --> Order["{services['order-worker']} Order Worker"]
        Payment --> DB["{services['database']} Database"]
        Payment --> Fraud["{services['fraud-detector']} Fraud Detector"]
        Checkout --> Cache["{services['cache-layer']} Cache Layer"]
        Order --> DB
    ```
    *(Legend: ✅ Healthy | ❌ Degraded | 🔍 Investigating)*
    """
    return topology

def obs_to_markdown(obs):
    md = f"### 🚨 Active Incident: {obs.incident_id} ({obs.task_name})\n"
    md += f"**Status:** {obs.current_status} | **Steps Remaining:** {obs.remaining_step_budget}\n\n"
    
    md += "#### 🗺️ System Topology\n"
    md += get_topology_map(obs) + "\n\n"
    
    md += f"**Affected Services:** {', '.join(obs.affected_services)}\n\n"
    md += f"> **Summary Explorer:** {obs.incident_summary}\n\n"
    
    if obs.known_alerts:
        md += "#### 🔔 Known Alerts\n"
        for a in obs.known_alerts:
            md += f"- [{a.severity.upper()}] **{a.service}**: {a.message}\n"
            
    if obs.feature_flag_states:
        md += "#### 🚩 Feature Flags\n"
        for f in obs.feature_flag_states:
            md += f"- **{f.flag_name}**: {'ENABLED' if f.enabled else 'DISABLED'} ({f.rollout_pct}%)\n"
            
    if obs.retrieved_logs:
        md += "#### 📜 Retrieved Logs\n"
        for svc, logs in obs.retrieved_logs.items():
            md += f"**{svc}**:\n"
            for log in logs[-3:]: # show last 3 for brevity
                md += f"  - `[{log.level}] {log.message}`\n"
                
    if obs.retrieved_metrics:
        md += "#### 📊 Retrieved Metrics\n"
        for svc, m in obs.retrieved_metrics.items():
            md += f"- **{svc}**: Errors: {m.error_rate_pct}% | Latency p99: {m.latency_p99_ms}ms | RPS: {m.requests_per_sec}\n"
            
    return md

def take_action(state, action_type, target_svc, severity, hypothesis, team, flag, msg_tpl):
    if not state or "env" not in state:
        return state, state["history"], "Please initialize the environment first.", gr.update()
        
    env = state["env"]
    
    if env.internal_state.resolved or env.internal_state.episode_step >= env.internal_state.max_steps:
        state["history"].append({"role": "assistant", "content": "Episode is already finished. Please reset."})
        return state, state["history"], "Episode Over.", gr.update(interactive=False)
        
    # Construct Action
    kwargs = {"action_type": ActionType(action_type)}
    if target_svc and target_svc != "None": kwargs["target_service"] = ServiceName(target_svc)
    if severity and severity != "None": kwargs["severity"] = SeverityLevel(severity)
    if hypothesis and hypothesis != "None": kwargs["hypothesis"] = RootCauseHypothesis(hypothesis)
    if team and team != "None": kwargs["team_name"] = TeamName(team)
    if flag and flag != "None": kwargs["target_flag"] = FeatureFlagName(flag)
    if msg_tpl and msg_tpl != "None": kwargs["message_template"] = MessageTemplate(msg_tpl)
    
    try:
        action = Action(**kwargs)
        obs = env.step(action)
        
        # Log to chat format
        action_str = f"Executed: {action.action_type.value}"
        if hasattr(action, 'target_service') and action.target_service: 
            action_str += f" on {action.target_service}"
        
        result_str = f"Result (Reward: {obs.reward:+.2f}):\n{obs.last_action_result}"
        if obs.done:
            result_str += f"\n\n*** EPISODE FINISHED ***\nFinal Score: {obs.final_score:.2f}"
            
        state["history"].append({"role": "user", "content": action_str})
        state["history"].append({"role": "assistant", "content": result_str})
        
        interactive = not obs.done
        return state, state["history"], obs_to_markdown(obs), gr.update(interactive=interactive)
        
    except Exception as e:
        import traceback
        error_msg = f"Error executing action: {str(e)}"
        print(traceback.format_exc())
        state["history"].append({"role": "assistant", "content": error_msg})
        return state, state["history"], "Error", gr.update()

# --- Gradio UI Layout ---
with gr.Blocks(title="IncidentOpsEnv Dashboard") as app:
    gr.Markdown("# 🔍 IncidentOpsEnv - Interactive SRE Dashboard")
    gr.Markdown("Step into the shoes of a Site Reliability Engineer tracking down production incidents. Select a simulation below to begin testing your hypothesis & command capabilities!")
    
    state_var = gr.State()
    
    with gr.Row():
        with gr.Column(scale=1):
            task_select = gr.Radio(["easy", "medium", "hard"], value="easy", label="1. Select Incident Difficulty")
            init_btn = gr.Button("🚀 Initialize Simulator", variant="primary")
            
            gr.Markdown("### 🕹️ Action Controls")
            action_type_dd = gr.Dropdown([e.value for e in ActionType], label="Action Type")
            target_svc_dd = gr.Dropdown(["None"] + [e.value for e in ServiceName], label="Target Service", value="None")
            severity_dd = gr.Dropdown(["None"] + [e.value for e in SeverityLevel], label="Severity Level", value="None")
            hyp_dd = gr.Dropdown(["None"] + [e.value for e in RootCauseHypothesis], label="Hypothesis", value="None")
            team_dd = gr.Dropdown(["None"] + [e.value for e in TeamName], label="Escalate to Team", value="None")
            flag_dd = gr.Dropdown(["None"] + [e.value for e in FeatureFlagName], label="Feature Flag Target", value="None")
            msg_dd = gr.Dropdown(["None"] + [e.value for e in MessageTemplate], label="Message Template", value="None")
            
            exec_btn = gr.Button("⚡ Execute Action", interactive=False)
            
        with gr.Column(scale=2):
            dashboard_display = gr.Markdown("### ⚠️ Dashboard Offline. Please Initialize.")
            
            chatbot = gr.Chatbot(label="Action & Event Log", height=400)
            
    # Wirings
    init_btn.click(
        fn=initialize_env,
        inputs=[task_select],
        outputs=[state_var, chatbot, dashboard_display, exec_btn]
    )
    
    exec_btn.click(
        fn=take_action,
        inputs=[state_var, action_type_dd, target_svc_dd, severity_dd, hyp_dd, team_dd, flag_dd, msg_dd],
        outputs=[state_var, chatbot, dashboard_display, exec_btn]
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)

from models import LogEntry
import random

def generate_noise_logs(service: str, count: int = 5) -> list[LogEntry]:
    messages = [
        "Metastore synchronization successful.",
        "Heartbeat received from node-7721.",
        "Cleanup of temporary session files completed.",
        "Request processed: 200 OK  latency 45ms.",
        "Garbage collection cycle finished in 12ms.",
        "Config reload triggered by filesystem watcher.",
        "User profile cache refreshed.",
    ]
    return [
        LogEntry(
            timestamp=f"2024-03-15T10:0{random.randint(0,5)}:{random.randint(10,59)}Z",
            level="INFO",
            service=service,
            message=random.choice(messages)
        ) for _ in range(count)
    ]

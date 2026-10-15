from message_bus import MessageDef

# Counters/rates cover window_us. Maxima and errors cover the full session.
TASK_PERFORMANCE = MessageDef("TaskPerformance", (
    ("task_id", "u", 0), ("task_name", "s", ""), ("target_hz", "f", 0.0),
    ("window_us", "u", 0), ("runs", "u", 0), ("measured_hz", "f", 0.0),
    ("skipped", "u", 0), ("avg_us", "f", 0.0), ("max_us", "u", 0),
    ("late_us", "u", 0), ("errors", "u", 0),
))

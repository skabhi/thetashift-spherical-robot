from message_bus import MessageDef

# Retained overwrites are normal for latest-sample topics, not an error.
BUS_STATUS = MessageDef("BusStatus", (
    ("topics", "u", 0), ("subscriptions", "u", 0), ("publications", "u", 0),
    ("retained_overwrites", "u", 0), ("subscriber_missed", "u", 0),
    ("queue_evictions", "u", 0), ("free_heap_bytes", "u", 0),
))

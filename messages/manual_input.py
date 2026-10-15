from message_bus import MessageDef

# Hardware-independent normalized input [-1, 1]; not a physical velocity.
# Consumer must check valid, enable_request and expiry before using it.
MANUAL_INPUT = MessageDef("ManualInput", (
    ("forward", "f", 0.0), ("sideways", "f", 0.0), ("turn", "f", 0.0),
    ("enable_request", "b", False), ("brake_request", "b", True),
    ("valid", "b", False), ("expires_us", "u", 0),
))

from message_bus import MessageDef

ROBOT_STATUS = MessageDef("RobotStatus", (
    ("mode", "s", "simulation"), ("actuators_enabled", "b", False),
    ("command_source", "u", 0), ("fault_flags", "u", 0),
    ("storage_available", "b", False), ("logger_enabled", "b", False),
))

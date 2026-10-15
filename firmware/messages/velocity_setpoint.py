from message_bus import MessageDef

# m/s and rad/s, positive yaw counterclockwise about +z.
VELOCITY_SETPOINT = MessageDef("VelocitySetpoint", (
    ("frame_id", "s", "internal_body"), ("vx", "f", 0.0),
    ("vy", "f", 0.0), ("yaw_rate", "f", 0.0),
    ("valid", "b", False), ("expires_us", "u", 0),
))

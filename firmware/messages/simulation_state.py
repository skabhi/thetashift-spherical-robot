from message_bus import MessageDef

# Unit quaternion rotates internal_body vectors into z-up world frame.
# Angular velocities are expressed in internal_body. No translational motion.
SIMULATION_STATE = MessageDef("SimulationState", (
    ("sample_time_us", "u", 0), ("scenario", "s", "stationary"),
    ("body_frame", "s", "internal_body"), ("world_frame", "s", "world_z_up"),
    ("q_w", "f", 1.0), ("q_x", "f", 0.0), ("q_y", "f", 0.0), ("q_z", "f", 0.0),
    ("omega_x", "f", 0.0), ("omega_y", "f", 0.0), ("omega_z", "f", 0.0),
    ("simulated", "b", True),
))

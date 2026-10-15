from message_bus import MessageDef

# Right-handed internal_body frame: x forward, y left, z up.
# Specific force (m/s^2), angular velocity (rad/s); valid_flags bit 0 accel,
# bit 1 gyro. A level stationary sensor measures +9.80665 on accel_z.
IMU_SAMPLE = MessageDef("ImuSample", (
    ("sample_time_us", "u", 0), ("frame_id", "s", "internal_body"),
    ("accel_x", "f", 0.0), ("accel_y", "f", 0.0), ("accel_z", "f", 0.0),
    ("gyro_x", "f", 0.0), ("gyro_y", "f", 0.0), ("gyro_z", "f", 0.0),
    ("valid_flags", "u", 0), ("simulated", "b", False),
))

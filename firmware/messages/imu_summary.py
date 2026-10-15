from message_bus import MessageDef

# Example task output: vector magnitudes, not an attitude estimate.
IMU_SUMMARY = MessageDef("ImuSummary", (
    ("sample_time_us", "u", 0), ("input_sequence", "u", 0),
    ("accel_magnitude", "f", 0.0), ("gyro_magnitude", "f", 0.0),
    ("valid", "b", False), ("simulated", "b", False),
))

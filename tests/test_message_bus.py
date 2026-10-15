"""Host checks for ownership, bounds, definitions, delivery and IMU physics."""
import math
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))

WRAP = 1 << 30
time.ticks_us = lambda: time.monotonic_ns() // 1000 % WRAP
time.ticks_diff = lambda a, b: (a - b + WRAP // 2) % WRAP - WRAP // 2
from message_bus import Bus, MessageDef, MonotonicClock
from messages import IMU_SAMPLE, SIMULATION_STATE, IMU_SUMMARY
from virtual_imu import VirtualIMU
from example_task import ExampleTask


class FakeClock:
    def __init__(self):
        self.value = 0
    def now_us(self):
        return self.value


class BusTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.bus = Bus(self.clock)
        self.definition = MessageDef('Counter', (("value", "u", 0),))
        self.topic = self.bus.advertise('counter', self.definition)

    def test_independent_subscribers_and_owned_copies(self):
        a, b = self.bus.subscribe('counter'), self.bus.subscribe('counter')
        payload = self.definition.new(value=1)
        self.topic.publish(payload)
        payload['value'] = 99
        first = a.read()
        first['value'] = 50
        self.assertEqual(b.read()['value'], 1)
        self.assertIsNone(a.read())
        self.assertEqual(self.topic.sequence, 1)

    def test_latest_and_missed_samples(self):
        sub = self.bus.subscribe('counter')
        for i in range(5):
            self.topic.publish(self.definition.new(value=i))
        self.assertEqual(sub.read()['value'], 4)
        self.assertEqual(sub.missed, 4)
        self.assertEqual(self.bus.subscriber_missed, 4)
        self.assertEqual(len(self.topic.buffer), 1)
        late = self.bus.subscribe('counter')
        self.assertEqual(late.read()['value'], 4)
        self.assertEqual(late.missed, 0)

    def test_queued_delivery_overflow_and_no_replay(self):
        topic = self.bus.advertise('events', self.definition, depth=2)
        sub = self.bus.subscribe('events')
        for i in range(4):
            topic.publish(self.definition.new(value=i))
        self.assertEqual(self.bus.queue_evictions, 2)
        self.assertEqual(sub.read()['value'], 2)
        self.assertEqual(sub.read()['value'], 3)
        self.assertEqual(sub.missed, 2)
        future = self.bus.subscribe('events', replay=False)
        self.assertFalse(future.updated())
        topic.publish(self.definition.new(value=4))
        self.assertEqual(future.read()['value'], 4)

    def test_invalid_publication_does_not_advance_sequence(self):
        for payload in ({}, {'bad': 1}, {'value': -1}, {'value': True}, {'value': 1, 'extra': 2}):
            with self.assertRaises(ValueError):
                self.topic.publish(payload)
        self.assertEqual(self.topic.sequence, 0)
        self.assertEqual(self.bus.publications, 0)

    def test_metadata_and_session(self):
        self.clock.value = 123
        self.topic.publish(self.definition.new(value=8), source_id=2)
        data = self.bus.subscribe('counter').read()
        self.assertEqual((data['timestamp_us'], data['sequence'], data['source_id'],
                          data['instance_id'], data['schema_version'], data['session_id']),
                         (123, 1, 2, 0, 1, 1))

    def test_bounds_and_cleanup(self):
        bus = Bus(self.clock, max_topics=1, max_subscriptions=1)
        bus.advertise('a', self.definition)
        with self.assertRaises(RuntimeError):
            bus.advertise('b', self.definition)
        sub = bus.subscribe('a')
        with self.assertRaises(RuntimeError):
            bus.subscribe('a')
        sub.close()
        sub.close()
        self.assertEqual(bus.subscription_count, 0)
        with self.assertRaises(RuntimeError):
            sub.read()
        bus.subscribe('a')

    def test_extend_schema_and_instances(self):
        schema = MessageDef('Custom', (("temperature_c", "f", 0.0),), version=2)
        topic = self.bus.advertise('custom', schema, instance=3)
        topic.publish(schema.new(temperature_c=21.5))
        data = self.bus.subscribe('custom', 3).read()
        self.assertEqual((data['temperature_c'], data['schema_version'], data['instance_id']), (21.5, 2, 3))

    def test_labels_exist_before_first_publication(self):
        topic = self.bus.advertise('performance', self.definition, instance=7, label='virtual_imu')
        self.assertEqual(topic.label, 'virtual_imu')
        self.assertEqual(topic.sequence, 0)
        self.assertIs(self.bus.advertise('performance', self.definition, instance=7), topic)
        with self.assertRaises(ValueError):
            self.bus.advertise('performance', self.definition, instance=7, label='motor')
        with self.assertRaises(ValueError):
            self.bus.advertise('invalid_label', self.definition, label='x' * 49)

    def test_clock_wrap(self):
        reading = [250]
        diff = lambda a, b: (a - b + 128) % 256 - 128
        clock = MonotonicClock(lambda: reading[0], diff)
        reading[0] = 5
        self.assertEqual(clock.now_us(), 11)
        reading[0] = 100
        self.assertEqual(clock.now_us(), 106)
        reading[0] = 0
        with self.assertRaises(RuntimeError):
            clock.now_us()

    def test_imu_scenarios_and_example(self):
        for name, schema in (('imu_sample', IMU_SAMPLE), ('simulation_state', SIMULATION_STATE), ('imu_summary', IMU_SUMMARY)):
            self.bus.advertise(name, schema)
        imu = VirtualIMU(self.bus)
        example = ExampleTask(self.bus)
        for scenario in imu.SCENARIOS:
            imu.set_scenario(scenario)
            self.clock.value += 250_000
            imu.step()
            example.step()
            sub = self.bus.subscribe('imu_summary')
            summary = sub.read()
            sub.close()
            self.assertAlmostEqual(summary['accel_magnitude'], 9.80665, places=5)
            self.assertTrue(summary['valid'] and summary['simulated'])
            state = self.bus.subscribe('simulation_state')
            data = state.read()
            state.close()
            self.assertAlmostEqual(sum(data[k] ** 2 for k in ('q_w', 'q_x', 'q_y', 'q_z')), 1.0)
            if scenario == 'stationary':
                self.assertEqual(summary['gyro_magnitude'], 0.0)
            if scenario == 'rotation':
                self.assertAlmostEqual(summary['gyro_magnitude'], .5)
        example.close()


if __name__ == '__main__':
    unittest.main()

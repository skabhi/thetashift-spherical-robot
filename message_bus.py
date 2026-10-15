"""Bounded, synchronous publish/subscribe for one cooperative event loop.

Not IRQ/thread safe. Publish copies scalar fields into an immutable tuple;
each subscription owns a cursor and copies received data into its own dict.
"""
from time import ticks_us, ticks_diff

HEADER = ("timestamp_us", "sequence", "source_id", "instance_id", "schema_version", "session_id")


class MonotonicClock:
    """Extended ticks, microseconds since construction, not wall-clock time.

    Poll more often than half the platform's ticks period. Robot publishers
    poll continuously; after a long stopped session construct a new bus/clock.
    """
    def __init__(self, reader=ticks_us, difference=ticks_diff):
        self.reader = reader
        self.difference = difference
        self.reset()

    def reset(self):
        self.last = self.reader()
        self.total = 0

    def now_us(self):
        now = self.reader()
        delta = self.difference(now, self.last)
        if delta < 0:
            raise RuntimeError("Clock not polled within half a ticks period")
        self.total += delta
        self.last = now
        return self.total


class MessageDef:
    """Fields are (name, kind, default); kinds u=unsigned int, f=number,
    b=bool, s=bounded string (<=48 characters). Fixed scalar layouts only.
    """
    def __init__(self, name, fields, version=1):
        self.name, self.fields, self.version = name, tuple(fields), version
        self.names = tuple(field[0] for field in self.fields)
        if version < 1 or len(set(self.names)) != len(self.names):
            raise ValueError("Invalid schema version or duplicate fields")
        for key, kind, value in self.fields:
            if key in HEADER or kind not in ("u", "f", "b", "s"):
                raise ValueError("Invalid field definition")
            self.validate(kind, value)

    @staticmethod
    def validate(kind, value):
        valid = ((kind == "u" and type(value) is int and value >= 0)
                 or (kind == "f" and type(value) in (int, float))
                 or (kind == "b" and type(value) is bool)
                 or (kind == "s" and type(value) is str and len(value) <= 48))
        if not valid:
            raise ValueError("Message field has invalid type or range")

    def new(self, **values):
        result = {key: default for key, _, default in self.fields}
        for key in values:
            if key not in result:
                raise ValueError("Unknown field: " + key)
        result.update(values)
        self.encode(result)
        return result

    def encode(self, values):
        if len(values) != len(self.fields):
            raise ValueError("Message must contain exactly the schema fields")
        encoded = []
        for key, kind, _ in self.fields:
            if key not in values:
                raise ValueError("Missing field: " + key)
            value = values[key]
            # Inline hot-path checks: a Python call per IMU field costs
            # measurable time on ESP32. Keep the same validation contract.
            value_type = type(value)
            if kind == "f":
                valid = value_type is float or value_type is int
            elif kind == "u":
                valid = value_type is int and value >= 0
            elif kind == "b":
                valid = value_type is bool
            else:
                valid = value_type is str and len(value) <= 48
            if not valid:
                raise ValueError("Message field has invalid type or range")
            encoded.append(value)
        return tuple(encoded)


class Topic:
    def __init__(self, bus, name, schema, instance, depth, label=""):
        self.bus, self.name, self.schema = bus, name, schema
        self.instance, self.depth = instance, depth
        self.label = label
        self.sequence = 0
        self.buffer = [None] * depth
        self.subscribers = []
        self.overwrites = 0

    def publish(self, values, source_id=0):
        if type(source_id) is not int or source_id < 0:
            raise ValueError("source_id must be unsigned")
        payload = self.schema.encode(values)
        timestamp = self.bus.clock.now_us()
        sequence = self.sequence + 1
        # Do not advance the sequence until validation and copying succeed.
        self.buffer[(sequence - 1) % self.depth] = (timestamp, source_id, payload)
        self.sequence = sequence
        self.bus.publications += 1
        if sequence > self.depth:
            self.overwrites += 1
            self.bus.retained_overwrites += 1
        if self.depth > 1:
            evicted = sequence - self.depth
            for sub in self.subscribers:
                lost = max(0, evicted - max(sub.cursor, sub.evicted_until))
                self.bus.queue_evictions += lost
                sub.evicted_until = max(sub.evicted_until, evicted)
        return sequence

    def copy_into(self, sequence, output):
        timestamp, source, payload = self.buffer[(sequence - 1) % self.depth]
        output.clear()
        for i, name in enumerate(self.schema.names):
            output[name] = payload[i]
        output.update(timestamp_us=timestamp, sequence=sequence, source_id=source,
                      instance_id=self.instance, schema_version=self.schema.version,
                      session_id=self.bus.session_id)
        return output


class Subscription:
    def __init__(self, topic, replay):
        self.topic = topic
        self.cursor = max(0, topic.sequence - 1) if replay else topic.sequence
        self.evicted_until = self.cursor
        self.missed = 0
        self.closed = False

    def updated(self):
        return not self.closed and self.topic.sequence > self.cursor

    def read_into(self, output):
        if self.closed:
            raise RuntimeError("Subscription closed")
        if not self.updated():
            return False
        topic = self.topic
        next_sequence = max(self.cursor + 1, topic.sequence - topic.depth + 1)
        missed = next_sequence - self.cursor - 1
        self.missed += missed
        topic.bus.subscriber_missed += missed
        topic.copy_into(next_sequence, output)
        self.cursor = next_sequence
        return True

    def read(self):
        output = {}
        return output if self.read_into(output) else None

    def close(self):
        if not self.closed:
            self.topic.subscribers.remove(self)
            self.topic.bus.subscription_count -= 1
            self.closed = True


class Bus:
    def __init__(self, clock=None, max_topics=32, max_subscriptions=64, session_id=1):
        self.clock = clock or MonotonicClock()
        self.max_topics, self.max_subscriptions = max_topics, max_subscriptions
        self.session_id = session_id
        self.topics = {}
        self.subscription_count = self.publications = 0
        self.retained_overwrites = self.subscriber_missed = self.queue_evictions = 0

    def advertise(self, name, schema, instance=0, depth=1, label=""):
        if not name or len(name) > 48 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in name):
            raise ValueError("Topic names use lowercase letters, digits and underscores")
        if type(instance) is not int or instance < 0 or not 1 <= depth <= 32:
            raise ValueError("Invalid instance or depth")
        if type(label) is not str or len(label) > 48:
            raise ValueError("Topic label must be a string of at most 48 characters")
        key = (name, instance)
        if key in self.topics:
            topic = self.topics[key]
            if topic.schema is not schema or topic.depth != depth:
                raise ValueError("Topic already registered with another definition")
            if label and topic.label != label:
                raise ValueError("Topic already registered with another label")
            return topic
        if len(self.topics) >= self.max_topics:
            raise RuntimeError("Topic limit reached")
        topic = Topic(self, name, schema, instance, depth, label)
        self.topics[key] = topic
        return topic

    def topic(self, name, instance=0):
        return self.topics[(name, instance)]

    def subscribe(self, name, instance=0, replay=True):
        if self.subscription_count >= self.max_subscriptions:
            raise RuntimeError("Subscription limit reached")
        topic = self.topic(name, instance)
        sub = Subscription(topic, replay)
        topic.subscribers.append(sub)
        self.subscription_count += 1
        return sub

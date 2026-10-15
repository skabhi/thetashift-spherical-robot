"""Validate a device trace and build a self-contained offline timeline."""
import argparse
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--trace', type=Path, default=ROOT / 'artifacts' / 'trace.json')
parser.add_argument('--output', type=Path, default=ROOT / 'artifacts' / 'timeline.html')
args = parser.parse_args()
raw = args.trace.read_text(encoding='utf-8')
events = json.loads(raw)['traceEvents']
assert events and all(e['ph'] == 'X' and e['dur'] >= 0 for e in events)
assert all(a['ts'] <= b['ts'] for a, b in zip(events, events[1:]))
html = (ROOT / 'tools' / 'timeline.html').read_text(encoding='utf-8')
html = html.replace('<script>', '<script>window.robotTrace=' + raw + ';</script><script>', 1)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(html, encoding='utf-8')
print('VALIDATED_EVENTS', len(events))
starts = [e['ts'] for e in events if e['name'] == 'motor']
gaps = [b-a for a, b in zip(starts, starts[1:])]
if gaps:
    print('Motor interval mean_us', round(mean(gaps), 1), 'min_us', min(gaps),
          'max_us', max(gaps), 'interval_hz', round(1_000_000 / mean(gaps), 3))
print('Open', args.output.resolve())

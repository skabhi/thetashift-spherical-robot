"""Validate the device trace and prepare offline viewers with it loaded."""
import json
from pathlib import Path
from statistics import mean

root = Path(__file__).parent
raw = (root / 'trace.json').read_text()
data = json.loads(raw)
events = data['traceEvents']
assert events and all(e['ph'] == 'X' and e['dur'] >= 0 for e in events)
assert all(a['ts'] <= b['ts'] for a, b in zip(events, events[1:]))
javascript = 'window.robotTrace=' + raw + ';'
(root / 'trace-data.js').write_text(javascript, encoding='utf-8')
html = (root / 'timeline.html').read_text(encoding='utf-8')
html = html.replace('<script src="trace-data.js"></script>',
                    '<script>' + javascript + '</script>')
(root / 'captured-timeline.html').write_text(html, encoding='utf-8')
print('VALIDATED_EVENTS', len(events))
for filename in ('trace-before-fix.json', 'trace.json'):
    if not (root / filename).exists():
        continue
    trace = json.loads((root / filename).read_text())['traceEvents']
    starts = [e['ts'] for e in trace if e['name'] == 'motor']
    gaps = [b-a for a, b in zip(starts, starts[1:])]
    if not gaps:
        print(filename, 'not enough motor events for interval analysis')
        continue
    print(filename, 'motor_events', len(starts), 'interval_mean_us', round(mean(gaps), 1),
          'interval_min_us', min(gaps), 'interval_max_us', max(gaps),
          'interval_hz', round(1_000_000 / mean(gaps), 3))
print('Built timeline.html data and standalone captured-timeline.html')

"""Check local handbook links and unique GitBook chapter navigation."""
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[1]
documents = [root / 'README.md'] + sorted((root / 'docs').rglob('*.md'))
link_pattern = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
checked = 0
broken = []
for document in documents:
    # Ignore example code when looking for actual document links.
    text = re.sub(r'```.*?```', '', document.read_text(encoding='utf-8'), flags=re.S)
    for target in link_pattern.findall(text):
        target = target.split(' "', 1)[0]
        parsed = urlsplit(target)
        if parsed.scheme or not parsed.path:
            continue
        checked += 1
        destination = (document.parent / unquote(parsed.path)).resolve()
        if not destination.exists():
            broken.append('{} -> {}'.format(document.relative_to(root), target))

summary = root / 'docs' / 'SUMMARY.md'
chapters = link_pattern.findall(summary.read_text(encoding='utf-8'))
assert len(chapters) == len(set(chapters)), 'Duplicate chapter in SUMMARY.md'
content_pages = {path.name for path in (root / 'docs').glob('*.md') if path.name != 'SUMMARY.md'}
assert set(chapters) == content_pages, 'Every handbook chapter must appear once in SUMMARY.md'
assert not broken, '\n'.join(broken)
print('PASS: {} Markdown files, {} local links, {} unique handbook chapters'.format(
    len(documents), checked, len(chapters)))

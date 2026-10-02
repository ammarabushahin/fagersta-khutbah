"""Add official X embedding to the existing isolated Nabd 2 app.
The account document and plaintext passwords are never needed by this patch.
"""
import hashlib
import json
from pathlib import Path
import sys
root = Path(sys.argv[1] if len(sys.argv) > 1 else 'nabd')
src = root / 'embed-src'
wall = (root / 'wall.html').read_text(encoding='utf-8')
if 'window.NabdXEmbeds = Object.freeze' in wall:
    raise SystemExit('Embed patch is already applied; rebuild Nabd 2 first.')
def once(old, new):
    global wall
    if wall.count(old) != 1:
        raise ValueError('Embed patch marker mismatch: ' + old[:80])
    wall = wall.replace(old, new, 1)
# Preserve live widget DOM when only counts, pinning, sizes, or toolbar state changes.
once('if(!old||old.dataset.signature!==markup){',
     'if(old&&old.classList.contains("x-embedded-card")){window.NabdXEmbeds.update(old,p);}else if(!old||old.dataset.signature!==markup){')
once('if(anchor!==el)feed.insertBefore(el,anchor||null);',
     'if(anchor!==el){if(el.isConnected&&typeof feed.moveBefore==="function")feed.moveBefore(el,anchor||null);else feed.insertBefore(el,anchor||null);}')
once('render();if(!isScreen&&!sharedMode)save();refresh();',
     (src / 'embeds.js').read_text(encoding='utf-8') + '\nrender();if(!isScreen&&!sharedMode)save();refresh();')
once('</head>', '<style>'+(src/'embeds.css').read_text(encoding='utf-8')+'</style><meta name="twitter:dnt" content="on"><meta name="nabd-renderer" content="official-x-widgets"></head>')
(root / 'wall.html').write_text(wall, encoding='utf-8')
shell = (root / 'index.html').read_text(encoding='utf-8').replace('<small>2.0</small>', '<small>2.1</small>')
(root / 'index.html').write_text(shell, encoding='utf-8')
report = json.loads((root / 'build-v2.json').read_text())
report.update(version='2.1.0', renderer='official-x-widgets', embedded_views_count_on_x=False)
report['files'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['index.html','wall.html']}
(root / 'build-v2.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'build-embed.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))

"""Synthetic filesystem/JSON worker for headless acknowledgement integration only."""
import json
import os
from pathlib import Path
import signal
import sys
import time
import uuid

mode, output, journal = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[sys.argv.index('--journal') + 1])
journal.parent.mkdir(parents=True, exist_ok=True)
output.mkdir()
(output / 'synthetic-marker.txt').write_text('synthetic output preserved\n')
info = output.stat()
entry = dict(schema=1, operation_id=str(uuid.uuid4()), pid=os.getpid(), phase='published',
             output=str(output), device=info.st_dev, inode=info.st_ino)
if mode == 'wrongOutput':
    entry['output'] = str(output.parent / 'other-output')
if mode == 'notPublished':
    entry['phase'] = 'publishing'
if mode == 'symlinkRecord':
    target = journal.with_suffix('.target')
    target.write_text(json.dumps(entry))
    journal.symlink_to(target)
else:
    journal.write_text(json.dumps(entry))
if mode == 'replacedOutput':
    output.rename(output.parent / 'original-output')
    output.mkdir()
    (output / 'replacement-marker.txt').write_text('unrelated output preserved\n')
if mode == 'missingRecord':
    journal.unlink()
if mode == 'pendingQuit':
    def complete_on_cancel(signum, frame):
        print(json.dumps(dict(event='complete', processed=2, patients=1, excluded_files=0)), flush=True)
        sys.exit(0)
    signal.signal(signal.SIGTERM, complete_on_cancel)
    print(json.dumps(dict(event='progress', processed=1, total_files=2)), flush=True)
    while True:
        time.sleep(0.02)
if mode == 'cancelled':
    print(json.dumps(dict(event='progress', processed=1, total_files=2)), flush=True)
    while True:
        time.sleep(0.02)
print(json.dumps(dict(event='complete', processed=2, patients=1, excluded_files=0)), flush=True)
if mode == 'malformed':
    print('{broken', end='', flush=True)
if mode == 'failedExit':
    sys.exit(7)

"""Private local operation records; never copied into published batch output."""
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid

class JournalError(Exception):
    pass

class OperationJournal:
    def __init__(self, path, destination):
        self.path = Path(path).absolute()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise JournalError('Recovery record location is unavailable.')
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        info = os.fstat(descriptor); os.close(descriptor)
        self.identity = (info.st_dev, info.st_ino)
        self.record = dict(schema=1, operation_id=str(uuid.uuid4()), pid=os.getpid(),
                           created=time.time(), phase='started', output=str(Path(destination).absolute()))
        self.mark('started')

    def mark(self, phase, staging=None, identity=None):
        info = self.path.lstat()
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != self.identity:
            raise JournalError('Recovery record ownership changed.')
        self.record['phase'] = phase
        if staging is not None:
            self.record.update(staging=str(Path(staging).absolute()), device=identity[0], inode=identity[1])
        descriptor, name = tempfile.mkstemp(prefix='.operation-', dir=self.path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(self.record, stream); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            info = self.path.lstat(); self.identity = (info.st_dev, info.st_ino)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

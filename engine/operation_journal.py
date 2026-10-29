"""Private local operation records; never copied into published batch output."""
import json
import os
from pathlib import Path
import stat
import time
import uuid

class JournalError(Exception):
    pass


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class OperationJournal:
    def __init__(self, path, destination):
        self.path = Path(path).absolute()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise JournalError('Recovery record location is unavailable.')
        parent = self.path.parent.lstat()
        self.parent_identity = (parent.st_dev, parent.st_ino)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        info = os.fstat(descriptor); os.close(descriptor)
        self.identity = (info.st_dev, info.st_ino)
        self.signature = _signature(info)
        self.failed = False
        self.record = dict(schema=1, operation_id=str(uuid.uuid4()), pid=os.getpid(),
                           created=time.time(), phase='started', output=str(Path(destination).absolute()))
        self.mark('started')

    def _check_parent(self):
        parent = self.path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or (parent.st_dev, parent.st_ino) != self.parent_identity:
            raise JournalError('Recovery record location changed.')

    def _check_record(self):
        self._check_parent()
        info = self.path.lstat()
        if not stat.S_ISREG(info.st_mode) or _signature(info) != self.signature:
            raise JournalError('Recovery record ownership changed.')

    def mark(self, phase, staging=None, identity=None):
        if self.failed:
            raise JournalError('Recovery record update has an uncertain prior outcome.')
        temporary = None
        temporary_identity = None
        directory = None
        try:
            self._check_record()
            directory = os.open(self.path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0))
            parent = os.fstat(directory)
            if (parent.st_dev, parent.st_ino) != self.parent_identity:
                raise JournalError('Recovery record location changed.')
            candidate = dict(self.record, phase=phase)
            if staging is not None:
                candidate.update(staging=str(Path(staging).absolute()), device=identity[0], inode=identity[1])
            # Create relative to the pinned parent: an ordinary directory swap
            # cannot redirect this operation's temporary into a replacement.
            name = '.operation-' + uuid.uuid4().hex
            temporary = self.path.parent / name
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0),
                                 0o600, dir_fd=directory)
            info = os.fstat(descriptor)
            temporary_identity = (info.st_dev, info.st_ino)
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(candidate, stream); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
                prepared = os.fstat(stream.fileno())
            # Detect ordinary concurrent replacement or in-place writes while
            # serializing/syncing. This is not an atomic conditional rename.
            self._check_record()
            if _signature(temporary.lstat()) != _signature(prepared):
                raise JournalError('Prepared recovery record changed.')
            os.replace(temporary, self.path)
            self._check_parent()
            info = self.path.lstat()
            if (not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != temporary_identity or
                    (info.st_mode, info.st_size, info.st_mtime_ns) !=
                    (prepared.st_mode, prepared.st_size, prepared.st_mtime_ns)):
                raise JournalError('Recovery record changed after replacement.')
            committed = _signature(info)
            os.fsync(directory)
            self._check_parent()
            if _signature(self.path.lstat()) != committed:
                raise JournalError('Recovery record changed during synchronization.')
            self.identity = temporary_identity
            self.signature = committed
            self.record = candidate
        except BaseException:
            # A later cleanup update must not overwrite an unconfirmed result.
            self.failed = True
            raise
        finally:
            try:
                if temporary is not None and directory is not None:
                    try:
                        # Anchor cleanup to the original directory even if its
                        # pathname was moved; never delete a substituted entry.
                        info = os.stat(temporary.name, dir_fd=directory, follow_symlinks=False)
                        if (info.st_dev, info.st_ino) == temporary_identity:
                            os.unlink(temporary.name, dir_fd=directory)
                    except FileNotFoundError:
                        pass  # Successful replacement consumes the temporary name.
                    except OSError:
                        if not self.failed:
                            raise
            finally:
                if directory is not None:
                    os.close(directory)

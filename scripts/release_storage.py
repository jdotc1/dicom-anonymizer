#!/usr/bin/env python3
"""Monitored release entry point; configuration and receipts remain local."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


class StorageGuardError(ValueError):
    pass


def executable():
    selected = os.environ.get('STORAGE_GUARD') or shutil.which('storage-guard')
    if not selected:
        raise StorageGuardError('Storage guard is required for allocating release actions; configure STORAGE_GUARD or PATH')
    return selected


def require_active(output):
    """Authenticate the live supervisor, then preflight the actual destination."""
    guard = executable()
    try:
        active = subprocess.run([guard, 'active'], capture_output=True, text=True)
        if active.returncode != 0:
            raise StorageGuardError('Allocating release actions require an authenticated storage-guard run')
        checked = subprocess.run([guard, 'check', '--path', str(Path(output).absolute())],
                                 capture_output=True, text=True)
        if checked.returncode != 0:
            raise StorageGuardError('Storage guard refused the release destination; preserve current inputs and partial outputs')
    except OSError as exc:
        raise StorageGuardError('Storage guard could not execute; no release writes were started') from exc


def supervise(arguments):
    """The guard owns the worker process group and monitors parsed output roots."""
    guard = executable()
    command = [guard, 'run', '--entry', str(Path(__file__).resolve()),
               '--interpreter', sys.executable, '--', *arguments]
    try:
        # Do not capture: keep guard warnings/refusals visible and preserve status.
        return subprocess.run(command).returncode
    except OSError as exc:
        raise StorageGuardError('Storage guard could not start the release worker') from exc


if __name__ == '__main__':
    # There is no environment-only bypass. The allocating Python APIs below
    # authenticate the guard against its live operation/ancestry record.
    import release
    raise SystemExit(release.main(monitored=True))

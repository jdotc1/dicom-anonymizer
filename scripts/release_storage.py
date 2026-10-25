#!/usr/bin/env python3
"""Monitored release entry point; configuration and receipts remain local."""
import argparse
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


def authenticate(guard):
    active = subprocess.run([guard, 'active'], capture_output=True, text=True)
    if active.returncode != 0:
        raise StorageGuardError('Allocating release actions require an authenticated storage-guard run')


def require_active(output):
    """Authenticate and attach this destination to the live parent's monitor."""
    guard = executable()
    destination = str(Path(output).absolute())
    try:
        authenticate(guard)
        checked = subprocess.run([guard, 'check', '--path', destination],
                                 capture_output=True, text=True)
        if checked.returncode != 0:
            raise StorageGuardError('Storage guard refused the release destination; preserve current inputs and partial outputs')
        if getattr(checked, 'stderr', ''):
            sys.stderr.write(checked.stderr)
        # Supported nested admission updates the authenticated parent's monitored
        # volumes and root registrations, including destinations on another volume.
        admitted = subprocess.run([guard, 'run', '--entry', str(Path(__file__).resolve()),
                                   '--interpreter', sys.executable, '--',
                                   '--admit-output', '--output', destination],
                                  capture_output=True, text=True)
        if getattr(admitted, 'stderr', ''):
            sys.stderr.write(admitted.stderr)
        if admitted.returncode != 0:
            raise StorageGuardError('Storage guard refused release destination admission; preserve current inputs and partial outputs')
        # A successful child cannot authorize writes after its supervisor vanished.
        authenticate(guard)
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


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if arguments[:1] == ['--admit-output']:
        parser = argparse.ArgumentParser(description='Authenticate nested output admission without writing output')
        parser.add_argument('--admit-output', action='store_true')
        parser.add_argument('--output', required=True, type=Path)
        parser.parse_args(arguments)
        try:
            authenticate(executable())
        except (StorageGuardError, OSError):
            parser.exit(1, 'Storage guard could not authenticate destination admission\n')
        return 0
    # There is no environment-only bypass. The allocating Python APIs below
    # authenticate the guard against its live operation/ancestry record.
    import release
    return release.main(arguments, monitored=True)


if __name__ == '__main__':
    raise SystemExit(main())

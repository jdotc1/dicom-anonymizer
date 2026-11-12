"""Shared timeout helpers for tests that wait on child processes.

Every subprocess timeout in the test suite goes through ``scaled`` so a loaded
runner can stretch all of them with DICOM_TEST_TIMEOUT_SCALE (default 1).
"""
import os
import threading


def scale():
    try:
        value = float(os.environ.get('DICOM_TEST_TIMEOUT_SCALE', '1'))
    except ValueError:
        return 1.0
    if value != value or value in (float('inf'), float('-inf')) or value < 1.0:
        return 1.0
    return min(value, 100.0)


def scaled(seconds):
    return seconds * scale()


def kill_after(proc, seconds):
    """Kill ``proc`` after a scaled deadline so a blocking pipe read cannot hang.

    Returns the timer; callers cancel it in a ``finally`` block.
    """
    def kill():
        if proc.poll() is None:
            proc.kill()
    timer = threading.Timer(scaled(seconds), kill)
    timer.daemon = True
    timer.start()
    return timer

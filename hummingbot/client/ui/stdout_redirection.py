#!/usr/bin/env python

from __future__ import unicode_literals
from prompt_toolkit.eventloop import get_event_loop
from prompt_toolkit.document import Document
from hummingbot.client.settings import MAXIMUM_LOG_PANE_LINE_COUNT

from contextlib import contextmanager
from collections import deque
from typing import Deque
import threading
import sys

__all__ = [
    'patch_stdout',
    'StdoutProxy',
]


@contextmanager
def patch_stdout(raw=False, log_field=None):
    proxy = StdoutProxy(raw=raw, log_field=log_field)

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Enter.
    sys.stdout = proxy
    sys.stderr = proxy

    try:
        yield
    finally:
        # Exit.
        proxy.flush()

        sys.stdout = original_stdout
        sys.stderr = original_stderr


class StdoutProxy(object):
    """
    Proxy object for stdout which captures everything and prints output inside
    the current application.
    """
    def __init__(self, raw=False, original_stdout=None, log_field=None):
        assert isinstance(raw, bool)
        original_stdout = original_stdout or sys.__stdout__

        self.original_stdout = original_stdout

        self._lock = threading.RLock()
        self._raw = raw
        self._buffer = []

        self.errors = original_stdout.errors
        self.encoding = original_stdout.encoding
        self.log_field = log_field
        self.log_lines: Deque[str] = deque()
        self.log_lines.append("Running logs\n")

    def _write_and_flush(self, text):
        if not text:
            return

        def write_and_flush():
            self.log_lines.extend(text.split("\n"))
            while len(self.log_lines) > MAXIMUM_LOG_PANE_LINE_COUNT:
                self.log_lines.popleft()
            new_text: str = "\n".join(self.log_lines)
            self.log_field.buffer.document = Document(text=new_text, cursor_position=len(new_text))

        get_event_loop().call_from_executor(write_and_flush)

    def _write(self, data):
        if '\n' in data:
            # When there is a newline in the data, write everything before the newline, including the newline itself.
            before, after = data.rsplit('\n', 1)
            to_write = self._buffer + [before, '\n']
            self._buffer = [after]

            text = ''.join(to_write)
            self._write_and_flush(text)
        else:
            # Otherwise, cache in buffer.
            self._buffer.append(data)

    def _flush(self):
        text = ''.join(self._buffer)
        self._buffer = []
        self._write_and_flush(text)

    def write(self, data):
        with self._lock:
            self._write(data)

    def flush(self):
        """
        Flush buffered output.
        """
        with self._lock:
            self._flush()

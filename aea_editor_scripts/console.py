"""Terminal niceties: wrapped label/value lines and a spinner.

Everything here degrades to plain text when the stream is not a terminal or
when CI is set, so a logged run gives one clean line per step, no escape codes
and no spinner frames. Only the animation goes: the output stays as verbose.
"""

import itertools
import os
import shutil
import sys
import textwrap
import threading

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
INTERVAL = 0.1

TICK = "✔"
CROSS = "✘"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

# Long lines are hard to read even on a wide terminal, so wrap well short of it.
MAX_WIDTH = 100
LABEL_WIDTH = 11


# What a CI system puts in CI to say so. Anything else, including empty, is not CI.
TRUTHY = ("1", "true", "yes", "on")


def in_ci():
    """Whether this is an unattended run, and so nothing may animate."""
    return os.environ.get("CI", "").strip().lower() in TRUTHY


def width():
    """How wide to wrap, honouring the terminal but not following it forever."""
    return min(shutil.get_terminal_size((80, 24)).columns, MAX_WIDTH)


def field(label, value, indent=2):
    """A "  Label:     value" line, wrapped with a hanging indent."""
    prefix = f"{'':<{indent}}{label + ':':<{LABEL_WIDTH}}"
    return textwrap.fill(value, width=width(), initial_indent=prefix,
                         subsequent_indent=" " * len(prefix))


def note(text, indent=4):
    """A wrapped continuation line, with no label."""
    pad = " " * indent
    return textwrap.fill(text, width=width(), initial_indent=pad, subsequent_indent=pad)


class Spinner:
    """A one-line progress indicator that resolves into a tick or a cross.

    Used as a context manager around a step that blocks for a while. Call
    finish() with the outcome; leaving the block without calling it counts as
    success unless an exception is in flight.
    """

    def __init__(self, label, stream=None, indent=2):
        self.label = label
        self.stream = stream or sys.stdout
        self.indent = " " * indent
        self.animated = bool(getattr(self.stream, "isatty", lambda: False)()) and not in_ci()
        self._stop = threading.Event()
        self._thread = None
        self._finished = False

    def __enter__(self):
        if self.animated:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finish(ok=exc_type is None)
        return False

    def _spin(self):
        for frame in itertools.cycle(FRAMES):
            if self._stop.is_set():
                return
            self.stream.write(f"\r{self.indent}{frame}  {self.label}")
            self.stream.flush()
            self._stop.wait(INTERVAL)

    def finish(self, ok=True):
        """Replace the spinner with its outcome. Safe to call more than once."""
        if self._finished:
            return
        self._finished = True
        self._stop.set()
        if self._thread:
            self._thread.join()
            self.stream.write("\r\033[2K")
        mark = TICK if ok else CROSS
        if self.animated:
            mark = f"{GREEN if ok else RED}{mark}{RESET}"
        self.stream.write(f"{self.indent}{mark}  {self.label}\n")
        self.stream.flush()

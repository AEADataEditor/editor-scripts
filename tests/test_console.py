"""Tests for the terminal helpers: wrapped label lines and the spinner."""
import time

import pytest

from aea_editor_scripts import console


@pytest.fixture(autouse=True)
def not_ci(monkeypatch):
    """Tests describe interactive behaviour unless they say otherwise."""
    monkeypatch.delenv("CI", raising=False)


class FakeStream:
    """A stream that can claim to be a terminal, or not."""

    def __init__(self, tty=False):
        self.tty = tty
        self.chunks = []

    def isatty(self):
        return self.tty

    def write(self, text):
        self.chunks.append(text)

    def flush(self):
        pass

    @property
    def text(self):
        return "".join(self.chunks)


# --- label/value lines --------------------------------------------------------

def test_a_field_line_is_indented_and_aligned():
    assert console.field("Changes", "content 3") == "  Changes:   content 3"


def test_a_short_label_pads_to_the_same_column():
    changes = console.field("Changes", "x")
    action = console.field("Action", "y")
    assert changes.index("x") == action.index("y")


def test_a_long_value_wraps_under_its_own_column():
    value = "word " * 60
    lines = console.field("Reason", value).splitlines()
    assert len(lines) > 1
    assert max(len(line) for line in lines) <= console.width()
    assert lines[1].startswith(" " * (2 + console.LABEL_WIDTH))
    assert lines[1].lstrip().startswith("word")


def test_a_note_wraps_at_its_own_indent():
    lines = console.note("word " * 60).splitlines()
    assert all(line.startswith("    ") for line in lines)
    assert max(len(line) for line in lines) <= console.width()


# --- the spinner --------------------------------------------------------------

def test_a_plain_stream_gets_one_line_with_a_tick():
    stream = FakeStream(tty=False)
    with console.Spinner("refresh-tools", stream=stream):
        pass
    assert stream.text == f"  {console.TICK}  refresh-tools\n"


def test_a_plain_stream_shows_no_escape_codes():
    stream = FakeStream(tty=False)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        spin.finish(ok=False)
    assert "\033" not in stream.text


def test_a_failure_ends_in_a_cross():
    stream = FakeStream(tty=False)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        spin.finish(ok=False)
    assert stream.text.strip().startswith(console.CROSS)


def test_a_terminal_animates_and_then_settles_on_a_green_tick():
    stream = FakeStream(tty=True)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        time.sleep(console.INTERVAL * 3)
        spin.finish(ok=True)
    assert any(frame in stream.text for frame in console.FRAMES)
    assert stream.text.endswith(f"  {console.GREEN}{console.TICK}{console.RESET}"
                                f"  refresh-tools\n")


def test_the_spinner_line_is_cleared_before_the_outcome():
    stream = FakeStream(tty=True)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        spin.finish(ok=True)
    assert "\r\033[2K" in stream.text


def test_finishing_twice_prints_one_outcome():
    stream = FakeStream(tty=False)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        spin.finish(ok=True)
        spin.finish(ok=False)
    assert stream.text.count("refresh-tools") == 1


def test_an_exception_leaves_a_cross_behind():
    stream = FakeStream(tty=False)
    try:
        with console.Spinner("refresh-tools", stream=stream):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert console.CROSS in stream.text


# --- unattended runs ----------------------------------------------------------

def test_ci_is_recognised_however_it_is_spelled(monkeypatch):
    for value in ("TRUE", "true", "1", "yes", " on "):
        monkeypatch.setenv("CI", value)
        assert console.in_ci()


def test_anything_else_is_not_ci(monkeypatch):
    for value in ("", "false", "0", "no"):
        monkeypatch.setenv("CI", value)
        assert not console.in_ci()


def test_an_unset_ci_is_not_ci(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    assert not console.in_ci()


def test_ci_keeps_a_terminal_from_animating(monkeypatch):
    monkeypatch.setenv("CI", "TRUE")
    stream = FakeStream(tty=True)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        time.sleep(console.INTERVAL * 3)
        spin.finish(ok=True)
    assert stream.text == f"  {console.TICK}  refresh-tools\n"


def test_ci_still_reports_a_failed_step(monkeypatch):
    monkeypatch.setenv("CI", "TRUE")
    stream = FakeStream(tty=True)
    with console.Spinner("refresh-tools", stream=stream) as spin:
        spin.finish(ok=False)
    assert stream.text == f"  {console.CROSS}  refresh-tools\n"


def test_the_wrap_width_never_exceeds_the_maximum():
    assert console.width() <= console.MAX_WIDTH

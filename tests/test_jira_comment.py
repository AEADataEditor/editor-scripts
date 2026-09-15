"""Tests for the automated-comment marker shared by Jira-posting scripts."""

from aea_editor_scripts import jira_comment as J


def test_the_body_starts_with_the_robot_marker():
    assert J.automated("Hello.").startswith(f"{J.ROBOT} Hello.")


def test_the_body_ends_with_an_italic_footer():
    assert J.automated("Hello.").endswith(J.FOOTER)
    assert J.FOOTER.startswith("_") and J.FOOTER.endswith("_")


def test_the_original_body_is_preserved_unmodified():
    body = "Line one.\n\n*Bold* and {quote}quoted{quote}."
    assert body in J.automated(body)

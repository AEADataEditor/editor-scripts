"""Tests for aea-pdf-append."""
from pypdf import PdfReader, PdfWriter

from aea_editor_scripts.pdf_append import append_pdfs, main


def make_pdf(path, widths):
    """Write a PDF with one blank page per width, so pages are identifiable."""
    writer = PdfWriter()
    for w in widths:
        writer.add_blank_page(width=w, height=792)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def widths(path):
    return [round(float(p.mediabox.width)) for p in PdfReader(path).pages]


def test_appends_in_place_in_order(tmp_path):
    base = make_pdf(tmp_path / "REPLICATION.pdf", [600, 601])
    extra = make_pdf(tmp_path / "extra.pdf", [700])
    assert append_pdfs(str(base), [str(extra)]) == 3
    assert widths(base) == [600, 601, 700]


def test_multiple_extras_and_output(tmp_path):
    base = make_pdf(tmp_path / "a.pdf", [600])
    e1 = make_pdf(tmp_path / "b.pdf", [700])
    e2 = make_pdf(tmp_path / "c.pdf", [800])
    out = tmp_path / "out.pdf"
    assert main([str(base), str(e1), str(e2), "-o", str(out)]) == 0
    assert widths(out) == [600, 700, 800]
    assert widths(base) == [600]


def test_missing_file_is_error(tmp_path, capsys):
    base = make_pdf(tmp_path / "a.pdf", [600])
    assert main([str(base), str(tmp_path / "nope.pdf")]) == 2
    assert "not found" in capsys.readouterr().err


def test_invalid_pdf_is_error_and_base_untouched(tmp_path):
    base = make_pdf(tmp_path / "a.pdf", [600])
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    assert main([str(base), str(bad)]) == 2
    assert widths(base) == [600]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.pdf", "bad.pdf"]

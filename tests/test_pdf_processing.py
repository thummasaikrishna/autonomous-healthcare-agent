import fitz
import pytest

from app.research.pdf_processor import PDFProcessingError, extract_pdf, list_pdf_files
from app.utils.text_utils import chunk_text


def _make_pdf(path, pages_text):
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_text_extraction(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _make_pdf(str(pdf_path), ["This is page one about clinical trials.", "This is page two with more findings."])

    extracted = extract_pdf(pdf_path)

    assert extracted.filename == "sample.pdf"
    assert len(extracted.pages) == 2
    assert "clinical trials" in extracted.pages[0].text
    assert not extracted.is_empty


def test_malformed_pdf_raises_clean_error(tmp_path):
    bad_path = tmp_path / "broken.pdf"
    bad_path.write_bytes(b"not a real pdf file")

    with pytest.raises(PDFProcessingError):
        extract_pdf(bad_path)


def test_missing_file_raises_error(tmp_path):
    with pytest.raises(PDFProcessingError):
        extract_pdf(tmp_path / "does_not_exist.pdf")


def test_metadata_preservation_via_chunking(tmp_path):
    pdf_path = tmp_path / "trial.pdf"
    _make_pdf(str(pdf_path), ["Patients were randomized into two groups. " * 20])

    extracted = extract_pdf(pdf_path)
    chunks = chunk_text(extracted.pages[0].text, chunk_size=200, chunk_overlap=40)

    assert len(chunks) >= 1
    for chunk in chunks:
        assert isinstance(chunk, str)
        assert len(chunk) > 0


def test_list_pdf_files(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"x")
    (tmp_path / "b.pdf").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")

    files = list_pdf_files(tmp_path)
    assert len(files) == 2
    assert all(f.suffix == ".pdf" for f in files)


def test_list_pdf_files_missing_directory(tmp_path):
    assert list_pdf_files(tmp_path / "nope") == []

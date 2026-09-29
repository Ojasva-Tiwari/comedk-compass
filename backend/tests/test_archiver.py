import hashlib
from pathlib import Path
from backend.app.ingestion.archiver import DocumentArchiver

def test_sha256_computation():
    content = b"Official COMEDK Counselling Test Document"
    expected = hashlib.sha256(content).hexdigest()
    assert DocumentArchiver.compute_sha256(content) == expected

def test_url_validation():
    assert DocumentArchiver.validate_url("https://www.comedk.org/member-institutions") is True
    assert DocumentArchiver.validate_url("http://example.com/test.pdf") is True
    assert DocumentArchiver.validate_url("not_a_valid_url") is False
    assert DocumentArchiver.validate_url("file:///etc/passwd") is False

def test_archiving_and_idempotency(tmp_path):
    archiver = DocumentArchiver(base_raw_dir=tmp_path)
    content = b"PDF dummy content"
    h1, path1, size1 = archiver.archive_content(content, 2026, "CUTOFF_PDF", "test_cutoff.pdf")
    
    assert path1.exists()
    assert size1 == len(content)
    assert path1.parent.name == "cutoff"

    # Re-archiving identical content does not duplicate
    h2, path2, size2 = archiver.archive_content(content, 2026, "CUTOFF_PDF", "test_cutoff.pdf")
    assert h1 == h2
    assert path1 == path2

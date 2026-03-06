"""Tests for document deduplication hashing."""

from legal.discovery_assistant.deduplicator import compute_hashes


def test_compute_hashes_returns_tuple():
    result = compute_hashes("test content")
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)


def test_same_content_same_hash():
    h1 = compute_hashes("identical document text")
    h2 = compute_hashes("identical document text")
    assert h1 == h2


def test_different_content_different_hash():
    h1 = compute_hashes("document version A")
    h2 = compute_hashes("document version B")
    assert h1[0] != h2[0]  # MD5
    assert h1[1] != h2[1]  # SHA-256


def test_empty_content():
    md5, sha256 = compute_hashes("")
    assert len(md5) == 32
    assert len(sha256) == 64

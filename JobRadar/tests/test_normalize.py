"""Tests for normalization and deduplication."""

from __future__ import annotations

import pytest

from jobradar.pipeline.normalize import (
    clean_string,
    fingerprint,
    normalize_key,
    raw_job_to_db_dict,
)


class TestCleanString:
    def test_basic_cleaning(self):
        assert clean_string("  Hello World  ") == "hello world"
        assert clean_string("Hello, World!") == "hello world"
        assert clean_string("Hello   World") == "hello world"

    def test_special_characters(self):
        assert clean_string("C++ Developer") == "c developer"
        assert clean_string("Node.js/React") == "node js react"
        assert clean_string("C# .NET") == "c net"

    def test_empty_string(self):
        assert clean_string("") == ""
        assert clean_string("   ") == ""


class TestNormalizeKey:
    def test_basic_normalization(self):
        key = normalize_key("Acme Corp", "Senior Engineer", "Remote")
        assert key == "acme corp|senior engineer|remote"

    def test_case_insensitive(self):
        key1 = normalize_key("ACME", "ENGINEER", "REMOTE")
        key2 = normalize_key("acme", "engineer", "remote")
        assert key1 == key2

    def test_punctuation_stripped(self):
        key1 = normalize_key("Acme, Inc.", "Sr. Engineer", "San Francisco, CA")
        key2 = normalize_key("Acme Inc", "Sr Engineer", "San Francisco CA")
        assert key1 == key2


class TestFingerprint:
    def test_deterministic(self):
        fp1 = fingerprint("Acme", "Engineer", "Remote")
        fp2 = fingerprint("Acme", "Engineer", "Remote")
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex length

    def test_different_inputs_different_hashes(self):
        fp1 = fingerprint("Acme", "Engineer", "Remote")
        fp2 = fingerprint("Acme", "Engineer", "On-site")
        assert fp1 != fp2

    def test_normalization_before_hash(self):
        # These should produce the same fingerprint after normalization
        fp1 = fingerprint("Acme Corp", "Senior Engineer", "Remote")
        fp2 = fingerprint("acme corp", "senior engineer", "remote")
        assert fp1 == fp2


class TestRawJobToDbDict:
    def test_conversion(self):
        class MockRawJob:
            title = "Software Engineer"
            company = "Acme Corp"
            company_url = "https://acme.com"
            location = "Remote"
            apply_url = "https://acme.com/jobs/123"
            source = "ats:greenhouse"
            posted_at = None
            salary_structured = None
            salary_text = None

        job = MockRawJob()
        result = raw_job_to_db_dict(job)

        assert result["title"] == "Software Engineer"
        assert result["company"] == "Acme Corp"
        assert result["company_url"] == "https://acme.com"
        assert result["location"] == "Remote"
        assert result["apply_url"] == "https://acme.com/jobs/123"
        assert result["source"] == "ats:greenhouse"
        assert result["tags"] == []
        assert result["min_salary"] is None
        assert result["max_salary"] is None
        assert "fingerprint_hash" in result
        assert len(result["fingerprint_hash"]) == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
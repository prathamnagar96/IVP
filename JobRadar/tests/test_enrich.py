"""Tests for enrichment: tag extraction and salary parsing."""

from __future__ import annotations

import pytest

from jobradar.pipeline.enrich import (
    extract_tags,
    parse_salary,
    enrich_job,
)


class TestExtractTags:
    def test_python_tags(self):
        text = "We are looking for a Python developer with Django experience"
        tags = extract_tags(text)
        assert "python" in tags
        assert "django" in tags

    def test_javascript_tags(self):
        text = "JavaScript/TypeScript developer needed for React and Node.js"
        tags = extract_tags(text)
        assert "javascript" in tags
        assert "typescript" in tags
        assert "react" in tags
        # node.js -> nodejs alias
        assert "javascript" in tags  # node.js maps to javascript

    def test_go_rust_tags(self):
        text = "Golang and Rust engineer for backend systems"
        tags = extract_tags(text)
        assert "go" in tags
        assert "rust" in tags

    def test_cloud_tags(self):
        text = "Experience with AWS, Kubernetes, Docker, and Terraform required"
        tags = extract_tags(text)
        assert "aws" in tags
        assert "kubernetes" in tags
        assert "docker" in tags
        assert "terraform" in tags

    def test_database_tags(self):
        text = "PostgreSQL, Redis, and MongoDB experience a plus"
        tags = extract_tags(text)
        assert "postgresql" in tags
        assert "redis" in tags
        assert "mongodb" in tags

    def test_no_duplicates(self):
        text = "Python python PYTHON developer"
        tags = extract_tags(text)
        assert tags.count("python") == 1

    def test_sorted_output(self):
        text = "React and AWS developer"
        tags = extract_tags(text)
        assert tags == sorted(tags)

    def test_empty_text(self):
        assert extract_tags("") == []
        assert extract_tags(None) == []

    def test_max_chars_limit(self):
        # Should not crash on very long text
        long_text = "Python " * 10000
        tags = extract_tags(long_text, max_chars=100)
        assert "python" in tags


class TestParseSalary:
    def test_k_range(self):
        min_sal, max_sal = parse_salary("$120k-$150k")
        assert min_sal == 120000
        assert max_sal == 150000

    def test_full_range(self):
        min_sal, max_sal = parse_salary("$120,000-$150,000")
        assert min_sal == 120000
        assert max_sal == 150000

    def test_up_to(self):
        min_sal, max_sal = parse_salary("Salary up to $150k")
        assert min_sal == 75000  # Half of max
        assert max_sal == 150000

    def test_salary_label(self):
        min_sal, max_sal = parse_salary("Salary: $120,000 - $150,000")
        assert min_sal == 120000
        assert max_sal == 150000

    def test_compensation_label(self):
        min_sal, max_sal = parse_salary("Compensation: $120k-$150k")
        assert min_sal == 120000
        assert max_sal == 150000

    def test_no_match(self):
        assert parse_salary("Competitive salary") == (None, None)
        assert parse_salary("") == (None, None)
        assert parse_salary(None) == (None, None)

    def test_different_dashes(self):
        # Test various dash characters
        for dash in ["-", "–", "—"]:
            min_sal, max_sal = parse_salary(f"$100k{dash}$120k")
            assert min_sal == 100000
            assert max_sal == 120000


class TestEnrichJob:
    def test_enrich_adds_tags_and_salary(self):
        job_dict = {
            "fingerprint_hash": "abc123",
            "title": "Python Engineer",
            "company": "Acme",
            "company_url": None,
            "location": "Remote",
            "tags": [],
            "min_salary": None,
            "max_salary": None,
            "apply_url": "https://acme.com/jobs/1",
            "source": "ats:greenhouse",
            "posted_at": None,
            "last_seen_at": None,
        }

        class MockRawJob:
            title = "Python Engineer"
            company = "Acme"
            company_url = None
            location = "Remote"
            description = "We need a Python developer with Django and AWS experience. Salary $120k-$150k"
            apply_url = "https://acme.com/jobs/1"
            source = "ats:greenhouse"
            posted_at = None
            salary_structured = None
            salary_text = "Salary $120k-$150k"

        result = enrich_job(job_dict, MockRawJob())

        assert "python" in result["tags"]
        assert "django" in result["tags"]
        assert "aws" in result["tags"]
        assert result["min_salary"] == 120000
        assert result["max_salary"] == 150000

    def test_structured_salary_preferred(self):
        job_dict = {
            "fingerprint_hash": "abc123",
            "title": "Engineer",
            "company": "Acme",
            "company_url": None,
            "location": "Remote",
            "tags": [],
            "min_salary": None,
            "max_salary": None,
            "apply_url": "https://acme.com/jobs/1",
            "source": "ats:lever",
            "posted_at": None,
            "last_seen_at": None,
        }

        class MockRawJob:
            title = "Engineer"
            company = "Acme"
            company_url = None
            location = "Remote"
            description = "Job description"
            apply_url = "https://acme.com/jobs/1"
            source = "ats:lever"
            posted_at = None
            salary_structured = (130000, 160000, "USD")
            salary_text = "Salary $100k-$120k"  # Different from structured

        result = enrich_job(job_dict, MockRawJob())

        # Should use structured salary, not regex
        assert result["min_salary"] == 130000
        assert result["max_salary"] == 160000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
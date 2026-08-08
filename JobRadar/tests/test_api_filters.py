"""Tests for API filters using test database."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from jobradar.api.main import create_app
from jobradar.config import Settings
from jobradar.db.models import Base, Job
from jobradar.db.client import DatabaseClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_app():
    """Create test app with in-memory database."""
    # Override settings for testing
    settings = Settings(
        supabase_url="postgresql://test:test@localhost/test",
        supabase_key="test",
        api_keys="test-key-123",
        rapidapi_proxy_secret="rapidapi-secret",
    )

    # Create test engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create test database client
    test_db = DatabaseClient(settings)
    test_db._engine = engine
    test_db._session_factory = session_factory

    # Override dependencies
    app = create_app(settings)

    # Monkey-patch the db client
    import jobradar.api.deps as deps_module
    original_get_db = deps_module.get_db

    def get_test_db():
        return test_db

    deps_module.get_db = get_test_db
    app.dependency_overrides[deps_module.get_db] = get_test_db

    yield app, test_db

    # Cleanup
    deps_module.get_db = original_get_db
    await engine.dispose()


@pytest.fixture
async def client(test_app):
    """Create test HTTP client."""
    app, _ = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def sample_jobs(test_app):
    """Insert sample jobs for testing."""
    _, test_db = test_app

    jobs = [
        {
            "fingerprint_hash": "hash1",
            "title": "Python Engineer",
            "company": "Acme Corp",
            "company_url": "https://acme.com",
            "location": "Remote",
            "tags": ["python", "django", "aws"],
            "min_salary": 120000,
            "max_salary": 150000,
            "apply_url": "https://acme.com/jobs/1",
            "source": "ats:greenhouse",
            "posted_at": "2026-01-15T10:00:00Z",
            "last_seen_at": "2026-01-15T10:00:00Z",
            "status": "active",
        },
        {
            "fingerprint_hash": "hash2",
            "title": "Frontend Engineer",
            "company": "Beta Inc",
            "company_url": "https://beta.com",
            "location": "San Francisco, CA",
            "tags": ["react", "typescript", "javascript"],
            "min_salary": 130000,
            "max_salary": 170000,
            "apply_url": "https://beta.com/jobs/1",
            "source": "ats:lever",
            "posted_at": "2026-01-14T10:00:00Z",
            "last_seen_at": "2026-01-14T10:00:00Z",
            "status": "active",
        },
        {
            "fingerprint_hash": "hash3",
            "title": "DevOps Engineer",
            "company": "Acme Corp",
            "company_url": "https://acme.com",
            "location": "Remote",
            "tags": ["aws", "kubernetes", "terraform", "go"],
            "min_salary": 140000,
            "max_salary": 180000,
            "apply_url": "https://acme.com/jobs/2",
            "source": "ats:ashby",
            "posted_at": "2026-01-13T10:00:00Z",
            "last_seen_at": "2026-01-13T10:00:00Z",
            "status": "active",
        },
        {
            "fingerprint_hash": "hash4",
            "title": "Expired Job",
            "company": "Gamma LLC",
            "company_url": "https://gamma.com",
            "location": "New York, NY",
            "tags": ["java", "spring"],
            "min_salary": 100000,
            "max_salary": 130000,
            "apply_url": "https://gamma.com/jobs/1",
            "source": "ats:greenhouse",
            "posted_at": "2025-01-01T10:00:00Z",
            "last_seen_at": "2025-01-01T10:00:00Z",
            "status": "expired",
        },
    ]

    async with test_db.session() as session:
        for job_data in jobs:
            job = Job(**job_data)
            session.add(job)
        await session.commit()


class TestJobsEndpoint:
    @pytest.mark.asyncio
    async def test_unauthorized(self, client):
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, client):
        response = await client.get("/api/v1/jobs", headers={"X-API-Key": "invalid"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_api_key(self, client, sample_jobs):
        response = await client.get("/api/v1/jobs", headers={"X-API-Key": "test-key-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_records"] == 3  # Only active jobs

    @pytest.mark.asyncio
    async def test_rapidapi_auth(self, client, sample_jobs):
        response = await client.get(
            "/api/v1/jobs",
            headers={"X-RapidAPI-Proxy-Secret": "rapidapi-secret"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_tag_filter(self, client, sample_jobs):
        response = await client.get(
            "/api/v1/jobs?tag=python",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_records"] == 1
        assert data["data"][0]["title"] == "Python Engineer"

    @pytest.mark.asyncio
    async def test_company_filter(self, client, sample_jobs):
        response = await client.get(
            "/api/v1/jobs?company=acme",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_records"] == 2
        assert all("Acme" in job["company"] for job in data["data"])

    @pytest.mark.asyncio
    async def test_min_salary_filter(self, client, sample_jobs):
        response = await client.get(
            "/api/v1/jobs?min_salary=135000",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_records"] == 1
        assert data["data"][0]["title"] == "DevOps Engineer"
        assert all(job["salary"]["min"] >= 135000 for job in data["data"] if job["salary"])

    @pytest.mark.asyncio
    async def test_pagination(self, client, sample_jobs):
        response = await client.get(
            "/api/v1/jobs?limit=2&page=1",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["page"] == 1
        assert data["limit"] == 2

        response = await client.get(
            "/api/v1/jobs?limit=2&page=2",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["page"] == 2

    @pytest.mark.asyncio
    async def test_limit_clamping(self, client, sample_jobs):
        # Limit > 100 should be clamped to 100
        response = await client.get(
            "/api/v1/jobs?limit=200",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 100

        # Limit < 1 should be clamped to 1
        response = await client.get(
            "/api/v1/jobs?limit=0",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 1

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, client, sample_jobs):
        response = await client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "test-key-123"},
        )
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limiting(self, client, sample_jobs):
        # Make requests up to limit
        for _ in range(100):
            response = await client.get(
                "/api/v1/jobs",
                headers={"X-API-Key": "test-key-123"},
            )
            assert response.status_code == 200

        # Next request should be rate limited
        response = await client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_app_lifespan_starts(self):
        settings = Settings(
            supabase_url="sqlite+aiosqlite:///:memory:",
            supabase_key="test",
            api_keys="test-key-123",
            rapidapi_proxy_secret="rapidapi-secret",
        )

        app = create_app(settings)
        async with app.router.lifespan_context(app):
            pass

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
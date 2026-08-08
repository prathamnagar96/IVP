"""Enrichment: tag extraction and salary parsing."""

from __future__ import annotations

import re
from typing import Any


# Canonical tag -> surface forms (aliases)
TAG_KEYWORDS: dict[str, list[str]] = {
    # Languages
    "python": ["python", "py3", "python3", "django", "flask", "fastapi", "pydantic"],
    "javascript": ["javascript", "js", "node.js", "nodejs", "node", "express", "nest", "nestjs"],
    "typescript": ["typescript", "ts", "tsx"],
    "go": ["go", "golang"],
    "rust": ["rust", "rustlang"],
    "java": ["java", "spring", "spring boot", "kotlin"],
    "kotlin": ["kotlin", "kt"],
    "csharp": ["c#", "csharp", ".net", "dotnet", "asp.net", "aspnetcore"],
    "cpp": ["c++", "cpp", "cplusplus"],
    "ruby": ["ruby", "rails", "ruby on rails"],
    "php": ["php", "laravel", "symfony"],
    "swift": ["swift", "ios", "swiftui"],
    "scala": ["scala", "akka", "play framework"],
    "elixir": ["elixir", "phoenix"],
    "clojure": ["clojure", "clojurescript"],
    "haskell": ["haskell"],
    "ocaml": ["ocaml", "reasonml"],
    "r": ["r language", "rlang"],
    "sql": ["sql", "postgresql", "postgres", "mysql", "sqlite", "mssql", "tsql"],

    # Frameworks & Libraries
    "react": ["react", "reactjs", "react.js", "next.js", "nextjs", "remix", "gatsby"],
    "vue": ["vue", "vuejs", "vue.js", "nuxt", "nuxtjs"],
    "angular": ["angular", "angularjs", "ng"],
    "svelte": ["svelte", "sveltekit"],
    "django": ["django", "djangorestframework", "drf"],
    "flask": ["flask"],
    "fastapi": ["fastapi", "starlette"],
    "express": ["express", "expressjs"],
    "nest": ["nest", "nestjs"],
    "spring": ["spring", "spring boot", "springboot"],
    "rails": ["rails", "ruby on rails", "ror"],
    "laravel": ["laravel"],
    "dotnet": [".net", "dotnet", "asp.net", "aspnetcore", "entity framework"],

    # Cloud & Infrastructure
    "aws": ["aws", "amazon web services", "ec2", "s3", "lambda", "rds", "dynamodb", "ecs", "eks", "fargate"],
    "gcp": ["gcp", "google cloud", "google cloud platform", "cloud run", "cloud functions", "bigquery"],
    "azure": ["azure", "microsoft azure", "azure functions", "aks"],
    "kubernetes": ["kubernetes", "k8s", "eks", "gke", "aks", "helm"],
    "docker": ["docker", "containerd", "podman"],
    "terraform": ["terraform", "iac", "infrastructure as code"],
    "ansible": ["ansible"],
    "prometheus": ["prometheus", "grafana", "observability"],
    "datadog": ["datadog"],
    "newrelic": ["new relic", "newrelic"],
    "cloudflare": ["cloudflare", "workers", "pages"],
    "vercel": ["vercel", "now.sh"],
    "netlify": ["netlify"],

    # Databases
    "postgresql": ["postgresql", "postgres", "pg"],
    "mysql": ["mysql", "mariadb"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "elasticsearch": ["elasticsearch", "elastic", "elk"],
    "clickhouse": ["clickhouse"],
    "cassandra": ["cassandra", "scylla"],
    "dynamodb": ["dynamodb"],
    "firebase": ["firebase", "firestore"],
    "supabase": ["supabase"],
    "planetscale": ["planetscale"],
    "neon": ["neon"],
    "cockroachdb": ["cockroachdb", "cockroach"],

    # Data & ML
    "machine-learning": ["machine learning", "ml", "mlops", "deep learning", "pytorch", "tensorflow", "keras", "jax"],
    "data-engineering": ["data engineering", "etl", "elt", "airflow", "dagster", "prefect", "dbt"],
    "analytics": ["analytics", "bi", "business intelligence", "tableau", "looker", "metabase"],
    "spark": ["spark", "pyspark", "databricks"],
    "kafka": ["kafka", "confluent", "redpanda", "event streaming"],
    "flink": ["flink"],
    "ray": ["ray", "ray.io"],

    # DevOps & Tools
    "ci/cd": ["ci/cd", "ci cd", "github actions", "gitlab ci", "jenkins", "circleci", "buildkite"],
    "git": ["git", "github", "gitlab", "bitbucket"],
    "linux": ["linux", "unix", "bash", "shell"],
    "nginx": ["nginx", "openresty"],
    "graphql": ["graphql", "apollo", "relay"],
    "rest": ["rest", "restful", "api design"],
    "grpc": ["grpc", "protobuf", "protocol buffers"],
    "websocket": ["websocket", "websockets", "socket.io"],
    "microservices": ["microservices", "service mesh", "istio", "linkerd"],

    # Frontend specifics
    "css": ["css", "scss", "sass", "tailwind", "styled-components", "emotion"],
    "html": ["html", "html5", "semantic html"],
    "webpack": ["webpack", "vite", "rollup", "esbuild", "turbopack"],
    "testing": ["testing", "jest", "vitest", "cypress", "playwright", "pytest", "unit test", "integration test"],
    "accessibility": ["accessibility", "a11y", "wcag"],

    # Mobile
    "ios": ["ios", "iphone", "ipad", "swiftui", "uikit"],
    "android": ["android", "kotlin", "jetpack compose"],
    "react-native": ["react native", "react-native", "expo"],
    "flutter": ["flutter", "dart"],

    # Security
    "security": ["security", "appsec", "devsecops", "penetration testing", "owasp"],
    "auth": ["authentication", "authorization", "oauth", "oidc", "saml", "jwt", "auth0", "clerk"],

    # Other
    "blockchain": ["blockchain", "web3", "ethereum", "solidity", "smart contracts", "defi"],
    "embedded": ["embedded", "firmware", "rtos", "arm", "stm32", "esp32"],
    "game-dev": ["game development", "unity", "unreal", "godot", "gamedev"],
}

# Pre-compiled regex for salary extraction
SALARY_PATTERNS = [
    # $120k-$150k, $120,000-$150,000
    re.compile(
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?\s*[-–—]\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?"
    ),
    # $120k - $150k (with spaces)
    re.compile(
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]\s*[-–—]\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]"
    ),
    # 120k-150k
    re.compile(
        r"\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]\s*[-–—]\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]\b"
    ),
    # up to $150k
    re.compile(
        r"up to\s+\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?"
    ),
    # $120k to $150k
    re.compile(
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?\s*(?:to|-)\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?"
    ),
    # Salary: $120,000 - $150,000
    re.compile(
        r"salary[:\s]+\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[-–—]\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
    ),
    # Compensation: $120k-$150k
    re.compile(
        r"compensation[:\s]+\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?\s*[-–—]\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?"
    ),
]


def extract_tags(text: str, max_chars: int = 5000) -> list[str]:
    """Extract tech stack tags from text using keyword matching.

    Args:
        text: Combined title + description text
        max_chars: Maximum characters to scan (for performance)

    Returns:
        List of unique canonical tags
    """
    if not text:
        return []

    # Limit text length for performance
    search_text = text.lower()[:max_chars]
    found_tags = set()

    for canonical_tag, aliases in TAG_KEYWORDS.items():
        for alias in aliases:
            # Use word boundaries for more accurate matching
            pattern = r"\b" + re.escape(alias.lower()) + r"\b"
            if re.search(pattern, search_text):
                found_tags.add(canonical_tag)
                break  # Found one alias, no need to check others for this tag

    return sorted(found_tags)


def parse_salary(text: str | None) -> tuple[int | None, int | None]:
    """Parse salary range from text using regex patterns.

    Returns:
        (min_salary, max_salary) in USD, or (None, None) if not found
    """
    if not text:
        return (None, None)

    for pattern in SALARY_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                min_val = _parse_salary_value(groups[0])
                max_val = _parse_salary_value(groups[1])
                if min_val and max_val and min_val <= max_val:
                    return (min_val, max_val)
            elif len(groups) == 1:
                # "up to" pattern
                max_val = _parse_salary_value(groups[0])
                if max_val:
                    return (max_val // 2, max_val)  # Rough estimate

    return (None, None)


def _parse_salary_value(value: str) -> int | None:
    """Parse salary string to integer (annual USD)."""
    try:
        clean = value.replace(",", "")
        num = float(clean)
        # If value looks like it's in thousands (e.g., 120, 150)
        if num < 1000:
            num *= 1000
        return int(num)
    except (ValueError, TypeError):
        return None


def enrich_job(job_dict: dict[str, Any], raw_job: Any) -> dict[str, Any]:
    """Enrich a job dict with tags and salary.

    Args:
        job_dict: Database dict from raw_job_to_db_dict
        raw_job: Original RawJob with description and salary fields

    Returns:
        Enriched job dict
    """
    # Combine title + description for tag extraction
    combined_text = f"{raw_job.title} {raw_job.description or ''}"

    # Extract tags
    tags = extract_tags(combined_text)
    job_dict["tags"] = tags

    # Parse salary - prefer structured, fall back to regex
    min_sal, max_sal = None, None

    if raw_job.salary_structured:
        min_sal, max_sal, _ = raw_job.salary_structured
    elif raw_job.salary_text:
        min_sal, max_sal = parse_salary(raw_job.salary_text)

    job_dict["min_salary"] = min_sal
    job_dict["max_salary"] = max_sal

    return job_dict
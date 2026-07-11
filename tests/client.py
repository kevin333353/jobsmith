"""Authenticated FastAPI test client plus the raw client for boundary tests."""
from fastapi.testclient import TestClient as _FastAPITestClient


class RawTestClient(_FastAPITestClient):
    """Raw boundary client using a production-allowed loopback Host."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("base_url", "http://localhost")
        super().__init__(*args, **kwargs)


class TestClient(RawTestClient):
    """Mirror a browser session by bootstrapping Jobsmith's API cookie."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        response = self.get("/api/session")
        assert response.status_code == 200

"""Regression tests for API input validation / security boundaries."""

import json


class TestGraphProjectDelete:
    """DELETE /api/graph/project/<id> must validate the project_id."""

    def test_invalid_id_too_short_returns_400(self, client):
        r = client.delete("/api/graph/project/ab")
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "error" in data

    def test_dots_in_id_returns_400(self, client):
        r = client.delete("/api/graph/project/..etc..passwd")
        assert r.status_code == 400

    def test_semicolon_injection_returns_400(self, client):
        r = client.delete("/api/graph/project/abc;rm%20-rf")
        assert r.status_code == 400


class TestSimulationGetValidation:
    """GET /api/simulation/<id> must validate the simulation_id."""

    def test_too_short_returns_400(self, client):
        r = client.get("/api/simulation/ab")
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "error" in data

    def test_dots_in_id_returns_400(self, client):
        r = client.get("/api/simulation/..etc..passwd")
        assert r.status_code == 400

    def test_command_injection_returns_400(self, client):
        r = client.get("/api/simulation/abc;rm%20-rf")
        assert r.status_code == 400


class TestSimulationHistoryRoute:
    """GET /api/simulation/history must NOT be caught by /<simulation_id>."""

    def test_history_returns_200(self, client):
        r = client.get("/api/simulation/history")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "simulations" in data


class TestReportGenerateValidation:
    """POST /api/report/generate must require project_id or graph_id."""

    def test_missing_ids_returns_400(self, client):
        r = client.post(
            "/api/report/generate",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "error" in data

    def test_empty_body_returns_400(self, client):
        r = client.post(
            "/api/report/generate",
            content_type="application/json",
        )
        assert r.status_code == 400

"""Smoke tests for all list API endpoints."""

import json


def test_list_projects_returns_200(client):
    r = client.get('/api/graph/project/list')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)


def test_list_simulations_returns_200(client):
    r = client.get('/api/simulation/list')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)


def test_list_reports_returns_200(client):
    r = client.get('/api/report/list')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)

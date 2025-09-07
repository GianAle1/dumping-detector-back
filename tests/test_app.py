import json
from unittest.mock import patch

import pytest

from app import app
from tasks import scrapear


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def dummy_run(producto, plataforma):
    return {"success": True, "productos": [], "archivo": "file.csv"}


def test_scrape_endpoint_returns_task_id(client):
    with patch("tasks.scrapear.run", side_effect=dummy_run):
        with patch("tasks.scrapear.delay") as mock_delay:
            mock_delay.side_effect = lambda *a, **kw: scrapear.apply(args=a, kwargs=kw)
            response = client.post(
                "/api/scrape", json={"producto": "test", "plataforma": "temu"}
            )
    assert response.status_code == 202
    data = response.get_json()
    assert "task_id" in data
    assert data["task_id"]


def test_resultado_endpoint_success(client):
    with patch("tasks.scrapear.run", side_effect=dummy_run):
        result = scrapear.apply(args=("test", "temu"))
    with patch("tasks.scrapear.AsyncResult", return_value=result):
        response = client.get(f"/api/resultado/{result.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["state"] == "SUCCESS"
    assert data["success"] is True
    assert data["productos"] == []
    assert data["archivo"] == "file.csv"


def test_scrape_endpoint_missing_params(client):
    response = client.post(
        "/api/scrape", json={"producto": "test"}
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "message" in data


def test_descargar_rejects_traversal_outside_data(client):
    response = client.get("/api/descargar/..%2Fapp.py")
    assert response.status_code == 404


def test_descargar_rejects_parent_directory_reference(client):
    response = client.get("/api/descargar/..")
    assert response.status_code == 404

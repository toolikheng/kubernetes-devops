import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "DevOps Platform API"}


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "dependencies": {"database": "connected"}}


def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content
    assert b"http_request_duration_seconds" in response.content


def test_create_item(client: TestClient) -> None:
    item_data = {"title": "Test Item", "description": "A test item"}
    response = client.post("/items", json=item_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
    assert data["description"] == "A test item"
    assert "id" in data


def test_list_items(client: TestClient) -> None:
    client.post("/items", json={"title": "Item 1", "description": "First"})
    client.post("/items", json={"title": "Item 2", "description": "Second"})
    response = client.get("/items")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 2


def test_get_item(client: TestClient) -> None:
    create_response = client.post("/items", json={"title": "Test", "description": "Desc"})
    item_id = create_response.json()["id"]
    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Test"


def test_update_item(client: TestClient) -> None:
    create_response = client.post("/items", json={"title": "Original", "description": "Old"})
    item_id = create_response.json()["id"]
    update_data = {"title": "Updated", "description": "New"}
    response = client.put(f"/items/{item_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


def test_delete_item(client: TestClient) -> None:
    create_response = client.post("/items", json={"title": "To Delete", "description": "X"})
    item_id = create_response.json()["id"]
    response = client.delete(f"/items/{item_id}")
    assert response.status_code == 204
    get_response = client.get(f"/items/{item_id}")
    assert get_response.status_code == 404

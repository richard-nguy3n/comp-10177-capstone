from app.app import app


def test_reject_empty_title():
    with app.test_client() as client:
        assert client.post("/api/records", json={"title": ""}).status_code == 400


def test_reject_bad_status():
    with app.test_client() as client:
        assert client.patch(
            "/api/records/1", json={"status": "invalid"}
        ).status_code == 400

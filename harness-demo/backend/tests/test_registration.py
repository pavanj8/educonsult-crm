def valid_payload(**overrides):
    payload = {
        "name": "Jane Student",
        "email": "jane@example.com",
        "password": "S3curePass!",
        "age": 22,
    }
    payload.update(overrides)
    return payload


def test_register_success(client):
    response = client.post("/students/register", json=valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert body["name"] == "Jane Student"
    assert "id" in body


def test_register_invalid_email(client):
    response = client.post("/students/register", json=valid_payload(email="not-an-email"))
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()


def test_register_duplicate_email(client):
    client.post("/students/register", json=valid_payload())
    response = client.post("/students/register", json=valid_payload(name="Someone Else"))
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_get_student(client):
    created = client.post("/students/register", json=valid_payload()).json()
    response = client.get(f"/students/{created['id']}")
    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"


def test_get_student_not_found(client):
    response = client.get("/students/999")
    assert response.status_code == 404


def test_list_students(client):
    client.post("/students/register", json=valid_payload())
    client.post("/students/register", json=valid_payload(email="second@example.com"))
    response = client.get("/students")
    assert response.status_code == 200
    assert len(response.json()) == 2

"""One walkthrough of the API: signup, dataset CRUD, ownership isolation, solve."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MECLABS_DB", str(tmp_path / "test.db"))
    from backend.main import app

    with TestClient(app) as c:
        yield c


def signup(client, email="a@b.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "password1"})
    assert r.status_code == 201, r.text
    return r.json()["user"]


def test_auth_and_dataset_lifecycle(client):
    assert client.get("/api/auth/me").status_code == 401

    user = signup(client)
    assert client.get("/api/auth/me").json()["user"] == user
    assert client.post(
        "/api/auth/signup", json={"email": "a@b.com", "password": "password1"}
    ).status_code == 409

    made = client.post("/api/datasets", json={"sample": "simple"}).json()
    ds_id = made["id"]
    assert made["data"]["classes"] == ["ClassA", "ClassB"]

    listed = client.get("/api/datasets").json()
    assert len(listed) == 1
    assert listed[0]["counts"] == {"classes": 2, "teachers": 3, "subjects": 3, "rooms": 2}
    assert listed[0]["has_solution"] is False

    edited = dict(made["data"], days=4)
    assert client.put(f"/api/datasets/{ds_id}", json={"name": "Renamed", "data": edited}).status_code == 204
    fetched = client.get(f"/api/datasets/{ds_id}").json()
    assert fetched["name"] == "Renamed"
    assert fetched["data"]["days"] == 4

    # a second user must not see, read or delete the first user's dataset
    client.post("/api/auth/logout")
    signup(client, "other@b.com")
    assert client.get("/api/datasets").json() == []
    assert client.get(f"/api/datasets/{ds_id}").status_code == 404
    assert client.delete(f"/api/datasets/{ds_id}").status_code == 404

    client.post("/api/auth/logout")
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401
    client.post("/api/auth/login", json={"email": "a@b.com", "password": "password1"})
    assert client.delete(f"/api/datasets/{ds_id}").status_code == 204
    assert client.get("/api/datasets").json() == []


def test_solve_endpoint_persists_solution(client):
    signup(client)
    ds_id = client.post("/api/datasets", json={"sample": "simple"}).json()["id"]

    result = client.post(f"/api/datasets/{ds_id}/solve", json={"time_limit": 30}).json()
    assert result["status"] in ("OPTIMAL", "FEASIBLE"), result
    assert not result["violations"]
    assert len(result["solution"]["class_timetables"]) == 2

    assert client.get("/api/datasets").json()[0]["has_solution"] is True
    assert client.get(f"/api/datasets/{ds_id}").json()["last_solution"]["status"] == result["status"]


def test_excel_round_trip(client):
    """The template we hand out must be readable by the importer that reads it back."""
    from backend.excel import template_bytes

    signup(client)
    blob = client.get("/api/import/template").content
    assert blob == template_bytes()

    parsed = client.post(
        "/api/import/parse",
        files={"file": ("template.xlsx", blob, "application/vnd.ms-excel")},
    ).json()
    sheets = {s["name"]: s for s in parsed["sheets"]}
    assert {"Classes", "Subjects", "Teachers", "Rooms"} <= set(sheets)
    assert sheets["Teachers"]["headers"][:2] == ["id", "name"]
    assert sheets["Teachers"]["rows"][0][0] == "MAT01"

    # CSV cells stay strings — coercing "007" to 7 would corrupt ids, and the
    # client coerces per mapped field anyway
    csv = b"id,type,capacity\nR1,standard,40\nR2,lab,25\n"
    rooms = client.post("/api/import/parse", files={"file": ("rooms.csv", csv, "text/csv")}).json()
    assert rooms["sheets"][0]["headers"] == ["id", "type", "capacity"]
    assert rooms["sheets"][0]["rows"] == [["R1", "standard", "40"], ["R2", "lab", "25"]]

    semi = b"id;type;capacity\nR9;lab;12\n"
    sniffed = client.post("/api/import/parse", files={"file": ("s.csv", semi, "text/csv")}).json()
    assert sniffed["sheets"][0]["headers"] == ["id", "type", "capacity"], "delimiter sniffing"

    assert client.post(
        "/api/import/parse", files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")}
    ).status_code == 400


def test_solution_xlsx_download(client):
    signup(client)
    ds_id = client.post("/api/datasets", json={"sample": "simple"}).json()["id"]
    assert client.get(f"/api/datasets/{ds_id}/solution.xlsx").status_code == 404

    client.post(f"/api/datasets/{ds_id}/solve", json={"time_limit": 30})
    r = client.get(f"/api/datasets/{ds_id}/solution.xlsx")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # a real zip, i.e. a real xlsx


def test_samples_listed(client):
    signup(client)
    keys = {s["key"] for s in client.get("/api/samples").json()}
    assert {"simple", "ktu", "hard"} <= keys

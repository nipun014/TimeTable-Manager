"""EduSchedule API. Thin HTTP layer over the CP-SAT engine in timetable_solver/."""
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import solve as run_solve

from .auth import COOKIE, current_user, hash_pw, set_cookie, start_session, verify_pw
from .db import db, init_db
from .excel import parse_upload, solution_bytes, template_bytes

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = {
    "simple": ("Simple (2 classes)", ROOT / "simple_sample.json"),
    "ktu": ("KTU S3+S5 (3-period labs)", ROOT / "ktu_sample.json"),
    "department": ("Department (20 classes, infeasible)", ROOT / "timetable_solver" / "sample_data.json"),
    "hard": ("Hard (12 classes, tight)", ROOT / "hard_sample.json"),
    "competitive": ("Competitive (9 classes)", ROOT / "competitive_example.json"),
}

DEFAULT_WEIGHTS = {
    "teacher_unavailable": 10,
    "teacher_idle_transition": 3,
    "class_consecutive_overrun": 4,
    "subject_spread_excess": 3,
    "heavy_back_to_back": 2,
    "teacher_early_late_imbalance": 2,
}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="EduSchedule", lifespan=lifespan)


def blank_dataset() -> dict:
    return {
        "institution": {"name": "", "scheme": "", "breaks": []},
        "days": 5,
        "periods_per_day": 6,
        "classes": [],
        "class_subjects": {},
        "subjects": {},
        "teachers": {},
        "rooms": {},
        "weights": dict(DEFAULT_WEIGHTS),
        "max_consecutive_periods": 3,
        "early_periods": [0, 1],
        "late_periods": [4, 5],
        "solver_config": {"max_time_seconds": 60, "num_workers": 8, "random_seed": 42},
    }


def counts(data: dict) -> dict:
    return {
        "classes": len(data.get("classes", [])),
        "teachers": len(data.get("teachers", {})),
        "subjects": len(data.get("subjects", {})),
        "rooms": len(data.get("rooms", {})),
    }


def owned(conn, dataset_id: int, user: dict):
    """404 rather than 403 on someone else's row — no existence leak."""
    row = conn.execute(
        "SELECT * FROM datasets WHERE id = ? AND user_id = ?", (dataset_id, user["id"])
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Dataset not found")
    return row


# ------------------------------------------------------------------ auth
class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(max_length=200)


class SignupBody(LoginBody):
    # only signup enforces a minimum; on login any wrong password must give the
    # same 401, never a 422 that says "too short"
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupBody):
    email = body.email.strip()
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email address")
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "That email is already registered")
        cur = conn.execute(
            "INSERT INTO users (email, pw) VALUES (?, ?)", (email, hash_pw(body.password))
        )
        user = {"id": cur.lastrowid, "email": email}
        token = start_session(conn, user["id"])
    res = JSONResponse({"user": user}, status_code=201)
    set_cookie(res, token)
    return res


@app.post("/api/auth/login")
def login(body: LoginBody):
    with db() as conn:
        row = conn.execute(
            "SELECT id, email, pw FROM users WHERE email = ?", (body.email.strip(),)
        ).fetchone()
        # same message either way, so this can't be used to enumerate accounts
        if row is None or not verify_pw(body.password, row["pw"]):
            raise HTTPException(401, "Invalid email or password")
        user = {"id": row["id"], "email": row["email"]}
        token = start_session(conn, user["id"])
    res = JSONResponse({"user": user})
    set_cookie(res, token)
    return res


@app.post("/api/auth/logout", status_code=204)
def logout(user: dict = Depends(current_user)):
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    res = Response(status_code=204)
    res.delete_cookie(COOKIE, path="/")
    return res


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": user}


# --------------------------------------------------------------- samples
@app.get("/api/samples")
def list_samples():
    out = []
    for key, (label, path) in SAMPLES.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append({
            "key": key,
            "label": label,
            "days": data.get("days", 5),
            "periods_per_day": data.get("periods_per_day", 6),
            **counts(data),
        })
    return out


# -------------------------------------------------------------- datasets
class NewDataset(BaseModel):
    name: str | None = None
    data: dict | None = None
    sample: str | None = None


class UpdateDataset(BaseModel):
    name: str | None = None
    data: dict | None = None


@app.get("/api/datasets")
def list_datasets(user: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, data, last_solution, updated_at FROM datasets "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user["id"],),
        ).fetchall()
    # counts computed here so the list page never downloads whole datasets
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "updated_at": r["updated_at"],
            "has_solution": r["last_solution"] is not None,
            "counts": counts(json.loads(r["data"])),
        }
        for r in rows
    ]


@app.post("/api/datasets", status_code=201)
def create_dataset(body: NewDataset, user: dict = Depends(current_user)):
    if body.sample:
        if body.sample not in SAMPLES:
            raise HTTPException(404, "Unknown sample")
        label, path = SAMPLES[body.sample]
        data = json.loads(path.read_text(encoding="utf-8"))
        name = body.name or label
    else:
        data = body.data or blank_dataset()
        name = body.name or "Untitled timetable"
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO datasets (user_id, name, data) VALUES (?, ?, ?)",
            (user["id"], name, json.dumps(data)),
        )
        new_id = cur.lastrowid
    return {"id": new_id, "name": name, "data": data}


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        row = owned(conn, dataset_id, user)
    return {
        "id": row["id"],
        "name": row["name"],
        "data": json.loads(row["data"]),
        "last_solution": json.loads(row["last_solution"]) if row["last_solution"] else None,
        "updated_at": row["updated_at"],
    }


@app.put("/api/datasets/{dataset_id}", status_code=204)
def update_dataset(dataset_id: int, body: UpdateDataset, user: dict = Depends(current_user)):
    """204 with no body on purpose: the builder autosaves on a debounce, and an
    empty response means no stale server payload can race a newer local edit."""
    with db() as conn:
        owned(conn, dataset_id, user)
        if body.name is not None:
            conn.execute(
                "UPDATE datasets SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (body.name, dataset_id),
            )
        if body.data is not None:
            conn.execute(
                "UPDATE datasets SET data = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(body.data), dataset_id),
            )
    return Response(status_code=204)


@app.delete("/api/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        owned(conn, dataset_id, user)
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    return Response(status_code=204)


# ----------------------------------------------------------------- solve
class SolveRequest(BaseModel):
    time_limit: int = 60
    seed: int = 42


@app.post("/api/datasets/{dataset_id}/solve")
def solve_dataset(dataset_id: int, body: SolveRequest, user: dict = Depends(current_user)):
    """Declared `def`, not `async def`, so FastAPI runs CP-SAT on the threadpool
    instead of blocking the event loop.

    ponytail: a sync solve holds one threadpool slot for up to 180s. Move to a
    job/poll model when deploying behind nginx (proxy_read_timeout defaults to
    60s) or when users need to cancel a run.
    """
    with db() as conn:
        row = owned(conn, dataset_id, user)
    time_limit = max(5, min(int(body.time_limit), 180))

    result = run_solve(row["data"], time_limit, int(body.seed))

    with db() as conn:
        conn.execute(
            "UPDATE datasets SET last_solution = ? WHERE id = ?",
            (json.dumps(result) if "solution" in result else None, dataset_id),
        )
    return result


# ---------------------------------------------------------------- excel io
@app.post("/api/import/parse")
async def import_parse(file: UploadFile = File(...)):
    """Hand back headers + rows. Which column means what is decided in the
    browser — no server-side import state to keep in sync."""
    blob = await file.read()
    try:
        return parse_upload(file.filename or "upload.xlsx", blob)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    except Exception:
        raise HTTPException(400, "Could not read that file — is it a valid .xlsx or .csv?")


@app.get("/api/import/template")
def import_template():
    return Response(
        template_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="eduschedule-template.xlsx"'},
    )


@app.get("/api/datasets/{dataset_id}/solution.xlsx")
def download_solution(dataset_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        row = owned(conn, dataset_id, user)
    if not row["last_solution"]:
        raise HTTPException(404, "This timetable has not been solved yet")
    result = json.loads(row["last_solution"])
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in row["name"]).strip() or "timetable"
    return Response(
        solution_bytes(result["solution"]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}.xlsx"'},
    )


# ------------------------------------------------------------ built frontend
# Registered last on purpose: a catch-all mounted before the routes above would
# swallow every /api call.
DIST = ROOT / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # the router lives in the browser, so any unknown path is a deep link
        # that has to be answered with index.html — not a 404
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")

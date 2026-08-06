# EduSchedule

Conflict-free academic timetables, solved with Google OR-Tools CP-SAT and built
through a browser — no JSON authoring required.

- **React + TypeScript** frontend (Vite)
- **FastAPI** backend with accounts, saved timetables and SQLite
- **CP-SAT** solving engine, unchanged, in `timetable_solver/`

---

## Run it

```powershell
# once
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend; npm install; cd ..
```

**Development** — two terminals, hot reload on both:

```powershell
# terminal 1 — API on :8000
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload `
  --reload-dir backend --reload-dir timetable_solver

# terminal 2 — UI on :5173  (proxies /api to :8000)
cd frontend; npm run dev
```

Open <http://localhost:5173>.

> The `--reload-dir` flags matter: plain `--reload` watches the whole working
> directory, `frontend/node_modules` included, and burns CPU reloading on noise.

**Single process** — build the UI once and let FastAPI serve it:

```powershell
cd frontend; npm run build; cd ..
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
```

Open <http://127.0.0.1:8000>. The built files are served only if
`frontend/dist` exists, so the dev flow is unaffected.

---

## Getting data in

Three ways, all interchangeable — mix them freely on the same timetable.

**1. The builder.** Every tab has a count box: type `18` next to Teachers, press
Apply, and 18 teachers appear ready to fill in. Add or remove them individually
too; the box stays in sync without ever fighting what you are typing. Shrinking a
count always asks first and names exactly what it would delete.

Teacher availability is a click-and-drag grid — drag to paint a run of periods,
click a day or period header to flip a whole row or column, or copy another
teacher's grid wholesale. Changing days or periods reshapes every grid at once,
so they can never drift out of sync with the week.

**2. Excel / CSV.** *Import* tab → download the template, or upload any
spreadsheet you already have. It guesses which sheet is which entity and which
column is which field; you correct it against a live preview, then merge. Merging
updates rows that match an existing id and appends the rest — it never deletes
what is already there.

**3. Raw JSON.** The *JSON* tab shows the exact payload the solver receives.
Paste, upload or download it. Useful as an escape hatch and for version control.

The **issue panel** at the top runs the same checks the solver's pre-validation
does, live: a subject nobody can teach, weekly hours that will not divide into
whole lab blocks, a room type no room has, a class whose subjects exceed the
week. Click any issue to jump to the field that caused it.

---

## The model

Decision variable `x[class][day][period][subject][teacher][room]`, created only
where the teacher can teach the subject and the room type matches.

| | Hard constraint |
|---|---|
| HC1 | one subject per class per slot |
| HC2 | a teacher is in one place at a time |
| HC3 | a room hosts one class at a time |
| HC4 | each subject gets **exactly** its weekly hours |
| HC5 | teacher availability is absolute |
| HC6 | subjects only run in rooms of the right type |
| HC7 | block subjects (3-period labs) run consecutively, same teacher and room |

Breaks blank out slots across every class. Everything else — teacher idle gaps,
consecutive-period limits, spreading a subject across the week, heavy subjects
back to back, early/late slot fairness — is a weighted penalty the solver
minimises. The Constraints tab is those weights.

---

## Layout

```
core.py                 solve() — the one entry point into the engine
timetable_solver/       data_loader · model · validator · generator
backend/
  main.py               all routes, then the SPA mount (must stay last)
  db.py                 sqlite3: users, sessions, datasets
  auth.py               scrypt hashing, opaque session tokens
  excel.py              spreadsheet parse / template / export
frontend/src/
  lib/                  types · api · builderReducer · validate · import · checks
  pages/                Auth · DatasetList · Builder · ImportTab · Result
  components/           CountRow · EntityTable · AvailabilityGrid · TimetableGrid
*.json                  sample datasets
```

Auth is a stdlib `hashlib.scrypt` hash plus a random opaque token in an httpOnly
cookie — no JWT, no crypto written by hand. The dev proxy makes `/api`
same-origin, so there is no CORS configuration and no token for the frontend to
hold. Every dataset query is scoped by `user_id` and answers 404, not 403, on
someone else's row.

Solve is a synchronous endpoint, so FastAPI runs CP-SAT on its worker threadpool
instead of blocking the event loop. It holds that slot for up to 180 seconds;
behind a reverse proxy with a shorter read timeout it would need a job/poll model
instead.

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # solver + API
cd frontend; npm run check                  # reducer, validation, import merge
npm run build                               # typecheck + production bundle
```

`npm run check` is plain `assert` statements bundled with the esbuild that
already ships inside Vite — no test framework, no config.

---

## Samples

| File | What it is |
|---|---|
| `simple_sample.json` | 2 classes, 3 subjects — solves instantly |
| `ktu_sample.json` | 6 classes, 18 teachers, 3-period labs, lunch break |
| `hard_sample.json` | 12 classes, tight capacity |
| `competitive_example.json` | 9 classes, 22 rooms |
| `timetable_solver/sample_data.json` | **deliberately impossible** — demonstrates pre-validation |

`ktu_sample.json` ships with availability grids one column wider than its
7-period day. They are reshaped on load and reported as a warning rather than
silently truncated, which is what used to inflate its reported teacher capacity
by 40 slots.

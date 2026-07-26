# Timetable Solver (package)

A minimal OR-Tools CP-SAT model for multi-class academic scheduling. It assigns
subjects, teachers, and rooms while enforcing teacher availability, room-type
compatibility, exact weekly hours, and double-period pairing.

For a complete architecture walkthrough and extension guide, read
[../SYSTEM_OVERVIEW.md](../SYSTEM_OVERVIEW.md).

## Modules

- `data_loader.py` — loads a JSON dataset and builds normalized structures
- `model.py` — builds the CP-SAT model (variables, hard constraints, soft objective)
- `solver.py` — entrypoint: load, validate, solve, print, render images, export JSON
- `validator.py` — pre-solve feasibility checks and post-solve constraint verification
- `generator.py` — JSON export utilities
- `sample_data.json` — example dataset schema

## Input

JSON only. See `sample_data.json` for the expected shape and
[../SYSTEM_OVERVIEW.md](../SYSTEM_OVERVIEW.md) for a field-by-field description.

By default the solver loads `sample_data.json`. To run against another dataset,
set the `DATA_FILE` environment variable (path is resolved relative to this
package directory), e.g. from the repo root:

```powershell
$env:DATA_FILE = "../hard_sample.json"; python -m timetable_solver.solver
```

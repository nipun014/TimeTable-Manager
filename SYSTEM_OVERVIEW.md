# System Overview: Timetable Solver

This guide explains how the system is structured, how the solver works, what data it expects, and how to extend it. If you read this end-to-end, you should be able to modify constraints, tune the objective, and add features confidently.

## TL;DR: Quickstart

```powershell
# From the repo root (Windows PowerShell)
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r timetable_solver/requirements.txt
python -m timetable_solver.solver
```

Outputs:
- Console tables for each class schedule
- `timetable.png`: per-class timetables
- `teacher_timetables.png`: per-teacher timetables
- `room_timetables.png`: per-room timetables
- `solution.json`: structured JSON export with utilization stats

## Repository Layout

- `timetable_solver/`
  - `data_loader.py`: Loads `sample_data.json` and builds normalized structures
  - `model.py`: Builds the OR-Tools CP-SAT model (variables, constraints, objective)
  - `solver.py`: Entrypoint—loads data, validates input, solves, prints, and renders timetables
  - `validator.py`: Pre-solver input validation and post-solver constraint verification
  - `generator.py`: JSON export utilities for solution data
  - `constraints.py`: Placeholder for custom constraint helpers (post-solve or auxiliary)
  - `requirements.txt`: Python dependencies
  - `sample_data.json`: Minimal dataset schema and example values
- `SYSTEM_OVERVIEW.md`: This document
- Other markdown files: supplementary notes and references

## Data Model (sample_data.json)

Top-level keys:
- `institution` (dict): Global configuration with `working_days`, `periods_per_day`, optional `blocked_slots`
- `classes` (list[str]): Class identifiers
- `class_subjects` (dict[str, list[str]]): Per-class curriculum mapping
- `subjects` (dict[str, SubjectInfo]): Subject catalog with attributes
- `teachers` (dict[str, TeacherInfo]): Teacher qualifications and availability
- `rooms` (dict[str, RoomInfo]): Room catalog and types
- `weights` (dict[str, int]): Soft constraint weights
- `solver_config` (dict): Solver parameters (`max_time_seconds`, `num_workers`, `log_progress`, `random_seed`)
- Optional tunables: `max_consecutive_periods`, `early_periods`, `late_periods`

Shapes and fields:
- SubjectInfo
  - `hours_per_week` (int): Exact weekly periods required per class
  - `room_type` (str): e.g., `standard`, `lab`, `computer`
  - `is_double_period` (bool): If true, must occur in two consecutive periods with same teacher/room
  - `is_indivisible` (bool): Reserved; double-period covers the primary indivisible use
  - `is_heavy` (bool): Counts toward “avoid back-to-back heavy subjects”
- TeacherInfo
  - `can_teach` (list[str]): Subjects the teacher can teach
  - `availability` (list[list[int]]): `days x periods` grid with 1=available, 0=unavailable
- RoomInfo
  - `type` (str): Must match `subject.room_type`
  - `capacity` (int): Informational in current model

`data_loader.load_data()` produces a normalized dictionary used by the model:
- `classes`, `days`, `periods_per_day`, `subjects`, `teachers`, `rooms`
- `teacher_info`, `room_info`, `subject_info`
- `raw` (original JSON)

## The Optimization Model (model.py)

Solver: OR-Tools CP-SAT (constraint programming with integer/Boolean variables).

### Decision Variables
- `x[c][d][p][s][t][r] ∈ {0,1}`: 1 if class `c` has subject `s` with teacher `t` in room `r` on day `d`, period `p`.
  - Created only when:
    - `t` can teach `s` (qualification), and
    - `room_info[r].type == subject_info[s].room_type` (compatibility)
- Presence summaries (internally derived for soft constraints):
  - `y_teacher[t][d][p]`: 1 if teacher `t` teaches anything at `(d,p)`
  - `y_class[c][d][p]`: 1 if class `c` has anything scheduled at `(d,p)`

### Hard Constraints (Feasibility)
1. **Class single-slot**: For each `(c,d,p)`, at most one assignment across all `(s,t,r)`
2. **Teacher conflict**: For each `(t,d,p)`, at most one assignment across all classes/subjects/rooms
3. **Room conflict**: For each `(r,d,p)`, at most one assignment across all classes/subjects/rooms
4. **Room type compatibility**: Enforced at variable creation (only compatible `(s,r)` pairs exist)
5. **Fixed horizon**: Only variables within `days × periods` exist by construction
6. **Subject frequency**: For each `(c,s)`, exactly `hours_per_week` occurrences across all days/periods/teachers/rooms
7. **Double-period**: If `s.is_double_period` and scheduled at `(d,p)` with `(t,r)`, must also be scheduled at `(d,p+1)` with the same `(t,r)`
8. **Teacher availability (hard)**: For each `(t,d,p)` where `availability[d][p] == 0`, enforce `x[...][t][...] == 0`
9. **Blocked periods**: Global break slots (e.g., lunch) prevent all scheduling at those `(d,p)` slots
10. **Teacher qualifications**: Enforced at variable creation (only `(s,t)` pairs where `s in can_teach` exist)

### Soft Constraints (Preferences) and Weights
Configured via `raw.weights` with defaults:
- `teacher_unavailable` (default 10): Penalizes scheduling when `teacher.availability[d][p] == 0`
- `teacher_idle_transition` (2): Penalizes changes between busy/free across adjacent periods for a teacher (reduces fragmentation)
- `class_consecutive_overrun` (3): Penalizes runs of class occupancy beyond `max_consecutive_periods`
- `subject_spread_excess` (2): Penalizes more than one occurrence of the same subject per day for a class
- `heavy_back_to_back` (1): Penalizes adjacent heavy subjects for a class
- `teacher_early_late_imbalance` (1): Penalizes imbalance between early vs. late load for each teacher

Objective: Minimize the sum of the above weighted penalties. In symbols: minimize $\sum_i w_i \cdot P_i$.

> Note: Teacher availability is enforced as a **hard constraint** (Phase 1 implementation). Unavailable slots are strictly prohibited from scheduling.

## Execution Flow (solver.py)

1. **Load data**: `data = load_data()`
2. **Pre-validation**: `pre_validation = pre_validate_input(data)`
   - Detects impossible configurations (hours > slots)
   - Validates teacher capacity (demand vs availability)
   - Checks room availability and type compatibility
   - Identifies constraint conflicts early
   - Displays [INFO], [WARN], and [ERROR] messages
   - Exits if critical errors detected
3. **Build model**: `model, x = build_model(data)`
4. **Configure solver**:
   - `max_time_seconds` (configurable via `solver_config`, default 60)
   - `num_workers` (configurable, default 8)
   - `log_progress` (configurable, default true)
   - `random_seed` (optional for deterministic mode)
5. **Solve**: `res = solver.Solve(model)`
6. **Post-solve validation**: `validation = validate_timetable(data, x, solver)`
   - Verifies all hard constraints satisfied
   - Reports any violations with constraint-by-constraint details
7. **On success** (`OPTIMAL` or `FEASIBLE`):
   - Print per-class tables to console
   - Display optimization score (objective value)
   - Render per-class image to `timetable.png`
   - Render per-teacher image to `teacher_timetables.png`
   - Render per-room image to `room_timetables.png`
   - Export structured data to `solution.json`

## Outputs

### Console Output
- Pre-validation summary with configuration info, warnings, and errors
- Per-class timetables (day/period grid with `Subject`, `Teacher`, `Room`)
- Optimization score (total penalty from soft constraints)
- Validation status ([OK] or [WARNING] with violation details)

### Visual Outputs (PNG)
- **`timetable.png`**: Per-class timetables with color-coded grids
- **`teacher_timetables.png`**: Per-teacher schedules showing class assignments
- **`room_timetables.png`**: Per-room utilization showing occupancy

### Structured Export (JSON)
- **`solution.json`**: Complete solution with:
  - Class timetables (all scheduled periods)
  - Teacher timetables (assignments and free periods)
  - Room utilization statistics (usage percentages)
  - Metadata (classes, days, periods, generation timestamp)

## Extending the System

- New hard constraints:
  - Pattern: Identify the set of relevant variables and add linear constraints using `model.Add(...)` and implications.
  - Example (strict availability): For each `(c,d,p,s,t,r)` where `availability[d][p] == 0`, enforce `x[c][d][p][s][t][r] == 0`.
- New soft preferences:
  - Create helper booleans/ints (`model.NewBoolVar`, `model.NewIntVar`), relate them to `x`/`y_*` with linear constraints, then add `weight * var` to the penalty list.
- Objective tuning:
  - Update `weights` in the JSON to rebalance trade-offs without changing code.
- New renderings/exports:
  - Add functions to traverse `x` for a given entity (class, teacher, room) and produce tables or files.

## Troubleshooting

### Pre-Validation Errors
- **[ERROR] Hours exceed available slots**: Reduce `hours_per_week` for some subjects or increase `periods_per_day`
- **[ERROR] Insufficient teacher capacity**: Add more teachers or reduce subject hours
- **[ERROR] Room shortage**: Add more rooms or verify room type compatibility
- **[ERROR] No qualified teachers**: Ensure each subject has at least one teacher in `can_teach`

### Solver Issues
- **No solution found**:
  - Review pre-validation warnings for capacity issues
  - Check `subjects[*].hours_per_week` vs. total available slots
  - Ensure room types exist for all subjects (`room_type` ↔ `rooms[*].type`)
  - Verify teacher availability matrices allow sufficient coverage
- **Poor schedules**:
  - Increase penalty weights for the aspects you care most about
  - Raise `max_time_seconds` for better search
  - Review optimization score to understand trade-offs
- **Performance**:
  - Reduce candidate combinations by pruning infeasible `(s,t,r)` pairs early
  - Start with fewer classes/subjects while iterating on model changes
  - Adjust `num_workers` based on available CPU cores

## Implemented Features

**Phase 1 (Critical Fixes):**
- ✅ Teacher availability as hard constraint (not soft penalty)
- ✅ Global break slots infrastructure (blocked periods)
- ✅ Post-solve validator with violation reporting
- ✅ Optimization score display

**Phase 2 (Essential Features):**
- ✅ Room timetable generation
- ✅ Per-class subject lists (curricula)
- ✅ JSON export with utilization stats
- ✅ Pre-solver input validation

**Phase 3 (Production Polish):**
- ✅ Deterministic mode (random seed configuration)
- ✅ Improved error messages and validation
- ✅ ASCII-safe console output for Windows

**Future Enhancements:**
- Teacher/class preferred time slots (soft constraints)
- Per-subject max periods per day
- Teacher workload limits (max periods/day or week)
- Scalability testing for 10+ classes

## Glossary

- CP-SAT: Constraint Programming SATisfiability solver from OR-Tools supporting integer variables
- Hard constraint: Must be satisfied; otherwise no solution
- Soft constraint: Preference to optimize; violations incur penalty but solution may still exist
- Double-period: A subject requiring two consecutive periods with the same teacher and room

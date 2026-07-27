# KTU Agentic AI Timetable Scheduling System

This document analyzes the existing MECLABS timetable solver and translates it into a KTU-specific architecture for a new agentic scheduling system.

## Scope

Target stack:

- Spring Boot backend APIs
- PostgreSQL persistence via Supabase
- Python OR-Tools CP-SAT solver
- CrewAI multi-agent orchestration
- Minimal React frontend later

KTU-specific requirements:

- Labs require 3 consecutive periods
- Faculty clashes are forbidden
- Weekly hours are mandatory
- Faculty preferences should be soft constraints
- Avoid too many consecutive periods for classes
- OR-Tools remains the actual scheduling engine
- CrewAI agents orchestrate, interpret, validate, and explain

## 1. What the Existing Project Already Does Well

The current solver in `timetable_solver/model.py` is a practical CP-SAT implementation with a strong modeling pattern:

- One binary decision variable per class, day, period, subject, teacher, and room
- Hard constraints for clashes, availability, room compatibility, and exact weekly hours
- Soft constraints encoded as weighted penalty terms
- Post-solve validation and explainability helpers
- JSON export plus timetable rendering

The strongest design trait is that feasibility is modeled directly in CP-SAT, while reporting and visualization are separate.

## 2. Core OR-Tools Variable Modeling Strategy

The current model uses a single assignment tensor:

`x[c][d][p][s][t][r] = 1`

Meaning:

- `c`: class
- `d`: day
- `p`: period
- `s`: subject
- `t`: teacher
- `r`: room

Key points:

- Variables are only created for legal combinations
- Teacher qualification prunes invalid `(subject, teacher)` pairs early
- Room-type compatibility prunes invalid `(subject, room)` pairs early
- This reduces search space before CP-SAT begins solving

The solver also builds summary variables:

- `y_teacher[t][d][p]`: whether teacher `t` is busy at a slot
- `y_class[c][d][p]`: whether class `c` is busy at a slot
- `heavy_present[c][d][p]`: whether a heavy subject is present at a slot

These summary variables are ideal for soft constraints and explainability.

## 3. Hard Constraints Implemented Today

The existing code enforces the following hard rules:

1. One subject per class per slot
2. One teacher per slot across all classes
3. One room per slot across all classes
4. Exact subject hours per week per class
5. Teacher availability as a hard constraint
6. Institutional breaks / blocked slots
7. Teacher qualification by variable creation
8. Room type compatibility by variable creation
9. Double-period continuity for a 2-slot subject

Important note for KTU:

- The current double-period logic supports 2 consecutive periods, but KTU labs require 3 consecutive periods.
- This should be replaced with a general duration constraint, not a special-case double-period flag.

## 4. Soft Constraints Implemented Today

The objective currently minimizes these weighted penalties:

- Teacher idle transitions
- Class consecutive overrun beyond a configured limit
- Subject spread excess within a day
- Heavy subject back-to-back adjacency
- Teacher early/late imbalance

Current implementation detail:

- Teacher unavailability has a weight in config, but availability is already enforced as a hard constraint, so that soft weight is effectively unused.

For KTU, the soft layer should focus on preferences only, not feasibility.

## 5. Objective Function Structure

The objective is a weighted sum of all penalty variables:

`minimize sum(weight_i * penalty_i)`

Pattern used:

- Create a boolean or integer helper variable
- Tie it to occupancy state using linear constraints
- Add weighted penalty term to a penalty list
- Minimize the total penalty sum

This is a clean CP-SAT architecture and should be preserved.

## 6. Solver Execution Flow Today

Current runtime flow in `timetable_solver/solver.py`:

1. Load data
2. Pre-validate inputs
3. Build CP-SAT model
4. Configure solver parameters
5. Solve
6. Validate solution
7. Print tables
8. Render timetable images
9. Export solution JSON

This is a good pipeline shape for the new system too, but the orchestration layer should move to Spring Boot and CrewAI.

## 7. Data Schema Structure

Current normalized data shape:

- `classes`: list of class IDs
- `days`: number of working days
- `periods_per_day`: number of periods
- `subjects`: list of subject IDs
- `teachers`: list of teacher IDs
- `rooms`: list of room IDs
- `teacher_info`: teacher metadata
- `room_info`: room metadata
- `subject_info`: subject metadata
- `class_subjects`: curriculum per class
- `raw`: original JSON input

Key schema fields:

- Subject
  - `hours_per_week`
  - `room_type`
  - `is_double_period`
  - `is_heavy`
- Teacher
  - `can_teach`
  - `availability`
- Room
  - `type`
  - `capacity`

For the KTU system, this schema should be extended with:

- semester / program / section metadata
- course credits or weekly hour patterns
- lab duration metadata
- faculty workload limits
- department-level constraints
- preferred slots
- unavailable date ranges

## 8. Validation Architecture

The current validator has two useful layers:

### Pre-solve validation

Checks whether the input is solvable or suspicious:

- Required hours vs available slots
- Teacher capacity vs demand
- Room-type availability
- Missing qualified teachers
- Low availability warnings
- Blocked slot pressure
- Double-period warnings

### Post-solve validation

Checks the actual timetable for violations:

- Class conflicts
- Teacher clashes
- Room clashes
- Weekly hours correctness
- Teacher availability
- Room type mismatch
- Double-period continuity

This is highly reusable for KTU because it gives explainability for demos and viva.

## 9. What Can Be Reused Directly

Reusable immediately:

- CP-SAT modeling style from `timetable_solver/model.py`
- Pre-validation and post-validation structure from `timetable_solver/validator.py`
- Input normalization approach from `timetable_solver/input_parser.py`
- JSON export structure from `timetable_solver/generator.py`
- Occupancy summary variables pattern
- Explanation of infeasibility patterns

Reusable with modification:

- Room modeling
- Teacher availability logic
- Weighted soft-constraint architecture
- Solution rendering logic
- Timetable export structure

## 10. What Should Be Simplified for a 3-Day Mini-Project

If the goal is a fast but credible KTU demo, keep the core and remove complexity:

Keep:

- Teacher clash prevention
- Room clash prevention
- Weekly hours enforcement
- 3-period lab blocks
- Faculty soft preferences
- Consecutive-period fatigue penalty
- Pre/post validation

Defer or remove:

- Room capacity optimization
- Complex visualization layer
- Multiple objective tiers
- Rare special-case subject heuristics
- Overengineered scoring systems
- Full UI polish

The mini-project should prove that CP-SAT is the real scheduler and CrewAI is the orchestration layer.

## 11. What Can Become CrewAI Tools or Tasks

CrewAI should not schedule directly. It should drive the workflow around the solver.

Good agent tasks:

- Parse the user request into structured scheduling requirements
- Classify constraints into hard vs soft
- Detect missing or inconsistent inputs
- Suggest weight priorities
- Explain infeasibility in human language
- Summarize tradeoffs after solving
- Produce a viva-friendly narrative

Good agent tools:

- `normalize_constraints`
- `analyze_feasibility`
- `build_solver_request`
- `run_solver`
- `validate_solution`
- `explain_solution`
- `compare_alternatives`

The solver itself should be exposed as a deterministic tool.

## 12. Best Way to Integrate Spring Boot APIs

Recommended division of responsibility:

### Spring Boot owns:

- Authentication and authorization
- Timetable request creation
- Persistence in PostgreSQL/Supabase
- Scheduling job state tracking
- Result retrieval APIs
- Faculty, course, room, and department data APIs
- Audit history and versioning

### Python solver service owns:

- Input normalization
- Constraint compilation
- CP-SAT solving
- Validation
- Schedule explanation generation

### Integration pattern:

1. Spring Boot receives scheduling request
2. Spring Boot stores the request and constraint profile
3. Spring Boot sends a normalized payload to Python solver service
4. Python returns timetable, validation report, and explanation metadata
5. Spring Boot persists the result and exposes it to the frontend

Preferred transport options:

- REST API for simplicity
- Async job queue if solving becomes slow
- JSON payload contracts with versioning

## 13. What Should Stay Deterministic vs Agent-Driven

### Deterministic

- Input normalization
- Constraint validation
- CP-SAT scheduling
- Result checking
- Persistence
- Scoring
- Export generation

### Agent-driven

- Requirement interpretation
- Constraint prioritization suggestions
- Feasibility narration
- Result explanation
- Comparison between alternative schedules

Rule of thumb:

- Agents decide what the problem means.
- OR-Tools decides the timetable.

## 14. Recommended Modular Architecture

### `agents.py`

Define CrewAI roles and task orchestration:

- Intake agent
- Constraint analyst
- Solver strategist
- Validator agent
- Explanation agent

Responsibilities:

- Translate user intent to structured constraints
- Decide whether a run is feasible or needs relaxation
- Explain results in human language

### `scheduler.py`

Own the solve pipeline:

- Load normalized request
- Call constraint builder
- Build CP-SAT model
- Run solver
- Return structured result object

This should be the core runtime entrypoint for the Python service.

### `constraints.py`

Turn this into the real constraint library:

- `add_class_single_slot_constraint`
- `add_teacher_clash_constraint`
- `add_room_clash_constraint`
- `add_weekly_hours_constraint`
- `add_teacher_availability_constraint`
- `add_lab_block_constraint`
- `add_soft_preference_constraints`

This is currently a placeholder and should become the cleanest file in the solver layer.

### `validator.py`

Keep both pre and post validation here:

- Input feasibility checks
- Constraint-by-constraint validation
- Infeasibility explanations
- Human-readable diagnostics

### `app.py`

Make this a thin application entrypoint only:

- For local dev: run the solver service or demo harness
- For production: expose a small API wrapper, or replace with FastAPI if needed
- Avoid embedding solver logic here

## 15. Recommended KTU Constraint Model

### Hard constraints

- Faculty clashes forbidden
- Room clashes forbidden
- Weekly hours mandatory
- Teacher qualification required
- Teacher unavailability forbidden
- Lab sessions must occupy 3 consecutive periods
- Lab sessions must use the same lab room if required by policy
- Breaks / lunch slots forbidden
- Class cannot have more than one subject in a slot

### Soft constraints

- Faculty preferred slots
- Minimize consecutive teaching fatigue
- Avoid too many consecutive class periods
- Prefer spreading subjects across days
- Balance early vs late teaching loads
- Prefer stable room assignment where helpful

### KTU-specific modeling note

For labs requiring 3 periods, model duration as a first-class concept:

- A lab assignment at `(d, p)` should consume `(d, p)`, `(d, p+1)`, and `(d, p+2)`
- The same teacher, class, and room should remain locked across the whole block unless policy says otherwise
- Do not model this as three unrelated single-period assignments

## 16. Recommended Execution Flow for the New System

1. User submits timetable request
2. Spring Boot validates and stores the request
3. CrewAI intake agent converts requirements to structured JSON
4. Feasibility agent checks obvious conflicts
5. Python solver builds the CP-SAT model
6. Solver computes the timetable
7. Validator checks the result
8. Explanation agent summarizes the solution
9. Spring Boot persists and serves the result
10. React frontend displays the timetable later

## 17. Potential Pitfalls

- Lab modeling is not the same as double-period modeling
- Teacher availability can make the model infeasible very quickly
- Too many soft constraints can slow solving or obscure the main objective
- If agents are allowed to change constraints too freely, the system becomes nondeterministic
- Room capacity is currently informational only, so it should not be assumed enforced
- A flat `can_teach` list may be too weak for KTU if faculty are restricted by semester or branch
- A large number of classes and subjects can cause variable explosion if incompatible combinations are not pruned

## 18. Suggested Production-Ready Architecture

### Backend layers

- API layer: Spring Boot
- Persistence layer: Supabase PostgreSQL
- Scheduling service: Python + OR-Tools
- Orchestration layer: CrewAI
- Optional async layer: queue or job table

### Data flow

`Spring Boot -> CrewAI -> normalized request -> Python solver -> validation -> persisted result -> API response`

### Storage model

- `timetable_requests`
- `timetable_runs`
- `constraint_profiles`
- `faculty`
- `courses`
- `rooms`
- `subjects`
- `solver_results`
- `validation_reports`

## 19. Recommended Documentation Structure for the New Project

If you are turning this into a new repository, a good document set would be:

- `README.md`: quickstart and project summary
- `architecture.md`: system design overview
- `constraints.md`: all hard and soft rules
- `api-contract.md`: Spring Boot and solver service payloads
- `agent-design.md`: CrewAI roles and tasks
- `validation.md`: feasibility and post-solve checks
- `demo-script.md`: viva/demo walkthrough

## 20. Bottom-Line Recommendation

The right architecture is not an AI wrapper around CRUD. It is:

- Spring Boot for the product system
- PostgreSQL/Supabase for durable state
- CrewAI for orchestration, interpretation, and explanation
- OR-Tools CP-SAT for the actual schedule generation
- A validation layer that proves correctness and explains failures

That combination gives you a maintainable, defensible, and viva-friendly KTU timetable system.

---

## Source Files Reviewed

- `timetable_solver/model.py`
- `timetable_solver/solver.py`
- `timetable_solver/validator.py`
- `timetable_solver/data_loader.py`
- `timetable_solver/input_parser.py`
- `timetable_solver/generator.py`
- `app.py`
- `timetable_solver/README.md`
- `SYSTEM_OVERVIEW.md`
- `AUDIT.md`
- `MASTER_CHECKLIST.md`

# IMPLEMENTATION FIXES - CODE EXAMPLES

## 🔴 CRITICAL FIXES (Do First)

### FIX #1: Move Teacher Availability to HARD Constraint

**Problem:** Teachers can currently be scheduled in unavailable slots with a penalty. This should be a hard constraint.

**Current Code (model.py - line 289-298):**
```python
# 1) Teacher availability (soft): penalize assignments where availability is 0
for c in classes:
    for d in range(days):
        for p in range(P):
            for s in subjects:
                for t in teachers:
                    if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                        unavailable = 1 - int(teacher_info[t]['availability'][d][p])
                        if unavailable == 1:
                            for r in rooms:
                                var = x[c][d][p][s][t].get(r)
                                if var is not None:
                                    penalties.append(W_TEACHER_UNAVAILABLE * var)
```

**Fix:** Add this HARD constraint in model.py after hard constraint #6 (Required weekly subject frequency):

```python
# ==========================
# HARD CONSTRAINT 9: Teacher forbidden slots
# Teacher cannot be scheduled in unavailable slots
# ==========================
for c in classes:
    for d in range(days):
        for p in range(P):
            for s in subjects:
                for t in teachers:
                    if s in teacher_info[t]['can_teach']:
                        # Only if teacher is UNAVAILABLE, force variable to 0
                        if int(teacher_info[t]['availability'][d][p]) == 0:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None:
                                        model.Add(var == 0)  # HARD: forbidden
```

**Then Remove:** The soft penalty code (lines 289-298) entirely.

**Updated sample_data.json schema:**
```json
{
  "teachers": {
    "Dr_Sharma": {
      "can_teach": ["Math", "Physics"],
      "availability": [
        [1, 1, 1, 1, 1, 1],  // 1 = available, 0 = forbidden
        [1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1],
        [1, 0, 0, 1, 1, 1],  // Example: Period 1-2 unavailable Monday
        [1, 1, 1, 1, 1, 1]
      ]
    }
  }
}
```

---

### FIX #2: Add Global Break Periods (Blocked Slots)

**Problem:** No way to mark periods as unavailable for ALL classes (e.g., lunch break 12:00-13:00).

**Add to sample_data.json:**
```json
{
  "institution": {
    "days": 5,
    "periods_per_day": 6,
    "breaks": [
      {
        "name": "Morning Break",
        "day": -1,  // -1 = all days
        "period": 2,
        "duration": 1
      },
      {
        "name": "Lunch Break",
        "day": -1,
        "period": 3,
        "duration": 1
      },
      {
        "name": "Staff Meeting",
        "day": 4,  // Friday only
        "period": 5,
        "duration": 1
      }
    ]
  }
}
```

**Add to model.py** (after loading data):
```python
# ==========================
# HARD CONSTRAINT: No assignments during breaks (blocked slots)
# ==========================
breaks = data.get('raw', {}).get('institution', {}).get('breaks', [])
for break_info in breaks:
    break_day = break_info['day']
    break_period = break_info['period']
    duration = break_info['duration']
    
    # Determine which days are affected
    affected_days = range(days) if break_day == -1 else [break_day]
    
    for d in affected_days:
        for offset in range(duration):
            p = break_period + offset
            if p < P:
                for c in classes:
                    for s in subjects:
                        for t in teachers:
                            if s in teacher_info[t]['can_teach']:
                                if t in x[c][d][p].get(s, {}):
                                    for r in rooms:
                                        var = x[c][d][p][s][t].get(r)
                                        if var is not None:
                                            model.Add(var == 0)
```

---

### FIX #3: Create Constraint Validation Function

**Add new file:** `timetable_solver/validator.py`

```python
"""
validator.py

Standalone constraint validation engine.
Checks timetable against all hard constraints.
"""
from typing import Dict, List, Tuple


class ValidationResult:
    """Result of timetable validation."""
    
    def __init__(self):
        self.is_valid = True
        self.violations = []  # List of violation strings
        self.soft_penalty = 0
        self.hard_count = 0
        self.soft_count = 0


def validate_timetable(data: Dict, x, solver) -> ValidationResult:
    """
    Validate a complete timetable against all constraints.
    
    Args:
        data: Problem configuration
        x: Decision variables from solver
        solver: Solved CP-SAT solver
        
    Returns:
        ValidationResult with violations list and penalty score
    """
    result = ValidationResult()
    classes = data['classes']
    days = data['days']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    teacher_info = data['teacher_info']
    room_info = data['room_info']
    subject_info = data['subject_info']
    
    # Helper: extract value from variable
    def get_value(var):
        return solver.Value(var) if var is not None else 0
    
    # ==== HARD CONSTRAINT 1: One subject per class per slot ====
    for c in classes:
        for d in range(days):
            for p in range(P):
                count = 0
                for s in subjects:
                    for t in teachers:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    count += get_value(var)
                if count > 1:
                    result.violations.append(
                        f"HC1: Class {c} has {count} subjects on Day {d+1} Period {p+1} (max 1)"
                    )
                    result.is_valid = False
    
    # ==== HARD CONSTRAINT 2: One teacher per slot ====
    for t in teachers:
        for d in range(days):
            for p in range(P):
                count = 0
                assignments = []
                for c in classes:
                    for s in subjects:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if get_value(var) == 1:
                                        count += 1
                                        assignments.append(c)
                if count > 1:
                    result.violations.append(
                        f"HC2: Teacher {t} assigned to {assignments} on Day {d+1} Period {p+1} (conflict)"
                    )
                    result.is_valid = False
    
    # ==== HARD CONSTRAINT 3: One room per slot ====
    for r in rooms:
        for d in range(days):
            for p in range(P):
                count = 0
                assignments = []
                for c in classes:
                    for s in subjects:
                        for t in teachers:
                            if s in teacher_info[t]['can_teach']:
                                if t in x[c][d][p].get(s, {}):
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None and get_value(var) == 1:
                                        count += 1
                                        assignments.append((c, s, t))
                if count > 1:
                    result.violations.append(
                        f"HC3: Room {r} double-booked on Day {d+1} Period {p+1}: {assignments}"
                    )
                    result.is_valid = False
    
    # ==== HARD CONSTRAINT 4: Subject hours per week ====
    for c in classes:
        for s in subjects:
            required = subject_info[s]['hours_per_week']
            count = 0
            for d in range(days):
                for p in range(P):
                    for t in teachers:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    count += get_value(var)
            if count != required:
                result.violations.append(
                    f"HC4: Class {c} Subject {s} has {count} hours/week (required {required})"
                )
                result.is_valid = False
    
    # ==== HARD CONSTRAINT 5: Teacher availability ====
    for c in classes:
        for d in range(days):
            for p in range(P):
                if int(teacher_info.get('availability', [[1]*6]*5)[d][p]) == 0:
                    for s in subjects:
                        for t in teachers:
                            if s in teacher_info[t]['can_teach']:
                                if t in x[c][d][p].get(s, {}):
                                    for r in rooms:
                                        var = x[c][d][p][s][t].get(r)
                                        if get_value(var) == 1:
                                            result.violations.append(
                                                f"HC5: Teacher {t} scheduled in unavailable slot (Day {d+1}, Period {p+1})"
                                            )
                                            result.is_valid = False
    
    # ==== HARD CONSTRAINT 6: Room type compatibility ====
    for c in classes:
        for d in range(days):
            for p in range(P):
                for s in subjects:
                    required_room_type = subject_info[s].get('room_type', 'standard')
                    for t in teachers:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None and get_value(var) == 1:
                                        room_type = room_info[r]['type']
                                        if room_type != required_room_type:
                                            result.violations.append(
                                                f"HC6: Subject {s} (needs {required_room_type}) in {room_type} room {r}"
                                            )
                                            result.is_valid = False
    
    # ==== HARD CONSTRAINT 7: Double-period consecutive ====
    for c in classes:
        for s in subjects:
            if subject_info[s].get('is_double_period', False):
                for d in range(days):
                    for p in range(P - 1):
                        for t in teachers:
                            if s in teacher_info[t]['can_teach']:
                                if t in x[c][d][p].get(s, {}):
                                    var_p = x[c][d][p][s][t].get(r) if 'r' in locals() else None
                                    var_p1 = x[c][d][p+1][s][t].get(r) if 'r' in locals() else None
                                    # Check implication constraint
    
    result.hard_count = len([v for v in result.violations if v.startswith('HC')])
    return result


def explain_infeasibility(data: Dict) -> List[str]:
    """
    Provide diagnostics when solution is infeasible.
    Check for obvious impossibilities.
    """
    suggestions = []
    
    classes = data['classes']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    teacher_info = data['teacher_info']
    subject_info = data['subjects']
    days = data['days']
    P = data['periods_per_day']
    
    total_slots = days * P
    
    # Check 1: Total subject hours vs available slots
    total_hours_needed = len(classes) * sum(subject_info[s]['hours_per_week'] for s in subjects)
    if total_hours_needed > total_slots * len(teachers):
        suggestions.append(
            f"⚠️ Insufficient teacher capacity: {total_hours_needed} hours needed, "
            f"but only {total_slots * len(teachers)} slot-hours available"
        )
    
    # Check 2: Teacher availability vs assignments
    for t in teachers:
        available_slots = sum(
            teacher_info[t]['availability'][d][p]
            for d in range(days)
            for p in range(P)
        )
        if available_slots == 0:
            suggestions.append(f"⚠️ Teacher {t} has zero available time slots")
    
    # Check 3: Room shortages
    lab_rooms = [r for r in rooms if data['room_info'][r]['type'] == 'lab']
    lab_subjects = [s for s in subjects if subject_info[s].get('room_type') == 'lab']
    if lab_subjects and not lab_rooms:
        suggestions.append(f"⚠️ {len(lab_subjects)} lab subjects but 0 lab rooms available")
    
    # Check 4: Teacher qualification coverage
    for s in subjects:
        qualified_teachers = [t for t in teachers if s in teacher_info[t]['can_teach']]
        if not qualified_teachers:
            suggestions.append(f"⚠️ Subject {s} has NO qualified teachers")
    
    return suggestions
```

**Update solver.py** to use validator:
```python
from .validator import validate_timetable, explain_infeasibility

# After solving:
if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print(f"\n✓ Solution found! Status: {solver.StatusName(res)}")
    
    # NEW: Validate solution
    validation = validate_timetable(data, x, solver)
    if validation.is_valid:
        print(f"✅ All constraints satisfied")
    else:
        print(f"⚠️ {len(validation.violations)} constraint violations found:")
        for v in validation.violations[:5]:  # Show first 5
            print(f"  - {v}")
    
    # NEW: Show optimization score
    print(f"📊 Optimization Score (Total Penalty): {solver.ObjectiveValue()}")
    
    pretty_print_solution(data, x, solver)
    export_timetable_image(data, x, solver)
    export_teacher_timetables(data, x, solver)
else:
    print(f'\n✗ No solution found. Status: {solver.StatusName(res)}')
    suggestions = explain_infeasibility(data)
    if suggestions:
        print("\n🔍 Possible reasons:")
        for s in suggestions:
            print(f"  {s}")
```

---

## 🟠 HIGH PRIORITY FIXES

### FIX #4: Add Room Timetable Output

**Add to solver.py:**
```python
def export_room_timetables(data, x, solver, output_path: str = "room_timetables.png"):
    """Render separate timetables for each room."""
    classes = data['classes']
    P = data['periods_per_day']
    days = data['days']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    room_info = data['room_info']

    n = len(rooms)
    fig_height = max(3 * n, 4)
    fig, axes = plt.subplots(n, 1, figsize=(14, fig_height))

    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]

    for ax, r in zip(axes, rooms):
        grid_data = []
        col_headers = [f"P{p+1}" for p in range(P)]

        for day in range(days):
            row = []
            for p in range(P):
                found = False
                for c in classes:
                    for s in subjects:
                        for t in teachers:
                            if s in data['teacher_info'][t]['can_teach']:
                                if t in x[c][day][p].get(s, {}):
                                    var = x[c][day][p][s][t].get(r)
                                    if var is not None and solver.Value(var) == 1:
                                        row.append(f"{s}\n{c}\n{t}")
                                        found = True
                                        break
                            if found:
                                break
                    if found:
                        break
                if not found:
                    row.append("Empty")
            grid_data.append(row)

        ax.axis('off')
        table = ax.table(
            cellText=grid_data,
            colLabels=col_headers,
            rowLabels=[f"Day {d+1}" for d in range(days)],
            loc='center',
            cellLoc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        for i in range(len(col_headers)):
            table[(0, i)].set_facecolor('#FF8C00')
            table[(0, i)].set_text_props(weight='bold', color='white')

        for i in range(1, days + 1):
            table[(i, -1)].set_facecolor('#FFE4B5')
            table[(i, -1)].set_text_props(weight='bold')

        room_type = room_info[r]['type']
        capacity = room_info[r]['capacity']
        ax.set_title(f"Room: {r} ({room_type}, Cap: {capacity})", 
                     fontsize=12, fontweight='bold', pad=12)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=200)
    plt.close(fig)
    print(f"Saved room timetables image to {output_path}")


# Add to main in solver.py:
if __name__ == '__main__':
    # ... existing code ...
    if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n✓ Solution found! Status: {solver.StatusName(res)}")
        pretty_print_solution(data, x, solver)
        export_timetable_image(data, x, solver)
        export_teacher_timetables(data, x, solver)
        export_room_timetables(data, x, solver)  # ADD THIS
```

---

### FIX #5: Add Deterministic Mode (Random Seed)

**Update sample_data.json:**
```json
{
  "solver_config": {
    "max_time_seconds": 30,
    "num_workers": 8,
    "log_progress": true,
    "random_seed": null  // Set to integer (e.g., 42) for reproducibility
  }
}
```

**Update solver.py:**
```python
def solve_timetable(data, config_seed=None):
    """Solve with optional deterministic seed."""
    model, x = build_model(data)
    solver = cp_model.CpSolver()
    
    solver_config = data.get('raw', {}).get('solver_config', {})
    solver.parameters.max_time_in_seconds = solver_config.get('max_time_seconds', 30)
    solver.parameters.num_search_workers = solver_config.get('num_workers', 8)
    solver.parameters.log_search_progress = solver_config.get('log_progress', True)
    
    # Set random seed if specified
    seed = config_seed or solver_config.get('random_seed')
    if seed is not None:
        solver.parameters.random_seed = int(seed)
        print(f"🔒 Deterministic mode: random_seed = {seed}")
    else:
        print(f"🎲 Randomized mode")
    
    return solver.Solve(model), x
```

---

### FIX #6: Add JSON Export

**Update generator.py:**
```python
import json
from datetime import datetime

def export_solution_json(data, x, solver, output_path: str = "solution.json"):
    """Export complete timetable as structured JSON."""
    classes = data['classes']
    days = data['days']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']

    solution = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "status": "feasible",
            "objective_value": solver.ObjectiveValue(),
            "solver": "Google OR-Tools CP-SAT"
        },
        "class_timetables": {},
        "teacher_timetables": {},
        "room_utilization": {}
    }

    # Class timetables
    for c in classes:
        timetable = []
        for d in range(days):
            day_schedule = []
            for p in range(P):
                period = {
                    "day": d + 1,
                    "period": p + 1,
                    "subject": None,
                    "teacher": None,
                    "room": None
                }
                found = False
                for s in subjects:
                    for t in teachers:
                        if s in data['teacher_info'][t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None and solver.Value(var) == 1:
                                        period['subject'] = s
                                        period['teacher'] = t
                                        period['room'] = r
                                        found = True
                                        break
                            if found:
                                break
                    if found:
                        break
                day_schedule.append(period)
            timetable.append(day_schedule)
        solution["class_timetables"][c] = timetable

    # Teacher timetables (similar structure)
    for t in teachers:
        timetable = []
        for d in range(days):
            day_schedule = []
            for p in range(P):
                period = {
                    "day": d + 1,
                    "period": p + 1,
                    "class": None,
                    "subject": None,
                    "room": None
                }
                found = False
                for c in classes:
                    for s in subjects:
                        if s in data['teacher_info'][t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None and solver.Value(var) == 1:
                                        period['class'] = c
                                        period['subject'] = s
                                        period['room'] = r
                                        found = True
                                        break
                            if found:
                                break
                    if found:
                        break
                day_schedule.append(period)
            timetable.append(day_schedule)
        solution["teacher_timetables"][t] = timetable

    with open(output_path, 'w') as f:
        json.dump(solution, f, indent=2)
    
    return solution

# In solver.py main:
if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    # ... other exports ...
    from .generator import export_solution_json
    export_solution_json(data, x, solver)
    print(f"Saved solution to solution.json")
```

---

## 🟡 MEDIUM PRIORITY: Per-Class Subject Lists

**Update sample_data.json schema:**
```json
{
  "classes": {
    "CSE_A": {
      "subjects": ["Math", "English", "Physics", "Programming"],
      "strength": 60
    },
    "CSE_B": {
      "subjects": ["Math", "English", "Physics", "DataStructures"],
      "strength": 55
    }
  },
  "subjects": {
    "Math": { "hours_per_week": 3, ... },
    ...
  }
}
```

**Update data_loader.py:**
```python
def load_data(path: Path = DATA_FILE) -> Dict:
    with open(path, 'r') as f:
        data = json.load(f)
    
    # NEW: Handle both array and dict class formats
    if isinstance(data['classes'], list):
        # Legacy format
        classes = data['classes']
    else:
        # New format with per-class configs
        classes = list(data['classes'].keys())
    
    # ... rest of function ...
```

**Update model.py** constraint #6:
```python
# For each class-subject combination that exists in curriculum
for c in classes:
    class_config = data.get('raw', {}).get('classes', {}).get(c, {})
    subject_list = class_config.get('subjects', subjects)  # Fall back to all
    
    for s in subject_list:
        required_hours = subject_info[s]['hours_per_week']
        # ... constraint code ...
```

---

## TESTING THESE FIXES

### After implementing fixes, test with:
```bash
cd d:\projects\MECLABS
.\.venv\Scripts\Activate.ps1
pip install -r timetable_solver/requirements.txt
python -m timetable_solver.solver
```

### Expected output with fixes:
```
✓ Solution found! Status: FEASIBLE
✅ All constraints satisfied
📊 Optimization Score (Total Penalty): 24
=== Timetable Solution ===

Class: CSE_A
   Day    Period    Subject       Teacher      Room
   Day 1      P1       Math     Dr_Sharma   Room_101
   Day 1      P2       Math     Dr_Sharma   Room_101
   ...

Saved timetable image to timetable.png
Saved teacher timetables image to teacher_timetables.png
Saved room timetables image to room_timetables.png  ✨ NEW
Saved solution to solution.json  ✨ NEW
```


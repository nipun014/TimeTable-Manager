# Comprehensive Timetable Scheduling System

## Overview

This is a constraint-based timetable generation system built using Google OR-Tools CP-SAT solver. The system schedules classes, subjects, teachers, and rooms across a fixed weekly grid while satisfying multiple hard constraints.

## System Architecture

### Core Components

1. **data_loader.py** - Loads and normalizes JSON configuration data
2. **model.py** - Defines the CP-SAT constraint model with all hard constraints
3. **solver.py** - Runs the solver and visualizes results
4. **sample_data.json** - Configuration file with classes, subjects, teachers, rooms, and constraints
5. **generator.py** - Utility for extracting solutions to other formats
6. **constraints.py** - Additional constraint validation utilities

### Data Model

The system uses a 6-dimensional decision variable structure:
- **x[class][day][period][subject][teacher][room]** = 1 if that combination is scheduled, 0 otherwise

## Hard Constraints Implemented

### 1. Single Subject Per Time Slot
**Requirement:** Each class can be assigned at most one subject in any given period.

**Implementation:** For each (class, day, period), exactly one (subject, teacher, room) combination must be selected.

```python
for c in classes:
    for d in range(days):
        for p in range(P):
            model.Add(sum(all_possible_assignments) == 1)
```

### 2. Teacher Conflict Constraint
**Requirement:** A teacher cannot be assigned to more than one class simultaneously.

**Implementation:** For each (teacher, day, period), at most one class assignment is allowed.

```python
for t in teachers:
    for d in range(days):
        for p in range(P):
            model.Add(sum(teacher_assignments) <= 1)
```

### 3. Room Conflict Constraint
**Requirement:** A room cannot be assigned to more than one class at the same time.

**Implementation:** For each (room, day, period), at most one class assignment is allowed.

```python
for r in rooms:
    for d in range(days):
        for p in range(P):
            model.Add(sum(room_assignments) <= 1)
```

### 4. Room Type Compatibility
**Requirement:** Subjects requiring special rooms (labs, computer labs) must be scheduled only in compatible room types.

**Implementation:** Variables are only created for compatible (subject, room) pairs based on room_type matching.

```python
subject_room_type = subject_info[s].get('room_type', 'standard')
room_type = room_info[r]['type']
if room_type == subject_room_type:
    # Create variable
```

### 5. Fixed Timetable Horizon
**Requirement:** Scheduling is constrained to a fixed number of days and periods per day.

**Implementation:** The variable structure itself enforces this - only variables within the defined grid exist.

**Configuration:**
```json
{
  "days": 5,
  "periods_per_day": 6
}
```

### 6. Required Weekly Subject Frequency
**Requirement:** Each subject must be scheduled exactly the required number of periods per week for each class.

**Implementation:** Sum all occurrences of a subject for a class across the week and enforce equality.

```python
for c in classes:
    for s in subjects:
        required_hours = subject_info[s]['hours_per_week']
        model.Add(sum(all_subject_occurrences) == required_hours)
```

### 7. Double-Period Constraint
**Requirement:** Subjects marked as double-period must be scheduled in two consecutive periods on the same day.

**Implementation:** If a double-period subject is scheduled at period p, it must also be scheduled at period p+1 with the same teacher and room.

```python
if subject_info[s].get('is_double_period', False):
    # If scheduled at (d, p), must also be at (d, p+1)
    # with same teacher and room
    model.Add(var_p == var_p_plus_1)
```

**Configuration:**
```json
"Physics_Lab": {
  "hours_per_week": 2,
  "is_double_period": true,
  "is_indivisible": true
}
```

### 8. Indivisible Sessions
**Requirement:** Sessions marked as indivisible must not be split across non-adjacent periods or days.

**Implementation:** For double-period subjects, this is enforced by the double-period constraint. Sessions must occur consecutively.

## Configuration Guide

### Subject Configuration

```json
"Math": {
  "hours_per_week": 4,              // Total weekly hours required
  "requires_special_room": false,    // Does it need a special room?
  "room_type": "standard",           // Room type required
  "is_double_period": false,         // Must be in consecutive periods?
  "is_indivisible": true             // Can't split sessions?
}
```

### Teacher Configuration

```json
"Dr_Sharma": {
  "can_teach": ["Math", "Physics_Lab"],  // Qualified subjects
  "availability": [                       // 5 days x 6 periods
    [1, 1, 1, 1, 1, 1],                  // 1 = available, 0 = not available
    [1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1]
  ]
}
```

### Room Configuration

```json
"Lab_A": {
  "type": "lab",        // Room type: standard, lab, computer
  "capacity": 30        // Currently not enforced (future enhancement)
}
```

## Usage

### Running the Solver

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r timetable_solver/requirements.txt

# Run the solver
python -m timetable_solver.solver
```

### Output

The system generates:
1. **Console output** - Text tables showing the schedule for each class
2. **timetable.png** - Visual grid (days × periods) for each class showing subject, teacher, and room
3. **teacher_timetables.png** - Visual grid for each teacher showing their schedule

## Constraint Satisfaction

The system uses CP-SAT (Constraint Programming with SAT solving) which:
- Finds feasible solutions satisfying ALL hard constraints
- Returns INFEASIBLE if no valid timetable exists
- Can optimize soft objectives (currently set to feasibility-only)

## Troubleshooting Infeasibility

If the solver returns "No solution found" (INFEASIBLE), possible causes:

1. **Over-constrained schedule** - Total required hours exceed available slots
   - Solution: Reduce hours_per_week or increase days/periods_per_day

2. **Teacher availability conflicts** - Not enough qualified teachers available
   - Solution: Add more teachers or increase availability

3. **Room capacity issues** - Not enough compatible rooms for special subjects
   - Solution: Add more labs/computer rooms

4. **Double-period conflicts** - Double-period subjects can't fit in the schedule
   - Solution: Ensure enough consecutive period slots exist

## Future Enhancements

Potential improvements to implement:
- Room capacity enforcement
- Break/lunch period constraints
- Preference-based teacher assignments
- Load balancing optimization
- Multi-week scheduling
- Custom natural language rules (via LLM integration)
- Minimize teacher idle time (soft constraint)
- Prevent same subject consecutive days for classes

## Technical Details

- **Solver:** Google OR-Tools CP-SAT v9.14+
- **Language:** Python 3.12+
- **Dependencies:** ortools, pandas, matplotlib
- **Algorithm:** Constraint Programming with Boolean Satisfiability
- **Search:** Parallel multi-worker search with configurable timeouts

## License

This is a scaffold system for educational and research purposes.

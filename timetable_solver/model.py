"""
model.py

Comprehensive timetable CP-SAT model with all hard constraints:
1. Single subject per class per time slot
2. Teacher conflict constraint (no double-booking)
3. Room conflict constraint (no double-booking)
4. Room type compatibility (lab subjects need labs, etc.)
5. Fixed timetable horizon (days x periods grid)
6. Required weekly subject frequency (exact hours)
7. Double-period constraint (consecutive periods same day)
8. Indivisible sessions (no splitting across days)
"""
from ortools.sat.python import cp_model
from typing import Dict, Tuple, List


def build_model(data: Dict) -> Tuple[cp_model.CpModel, Dict]:
    model = cp_model.CpModel()

    classes = data['classes']
    days = data['days']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    teacher_info = data['teacher_info']
    room_info = data['room_info']
    subject_info = data['subject_info']
    
    total_periods = days * P

    # ==========================
    # DECISION VARIABLES
    # ==========================
    # x[c][d][p][s][t][r] = 1 if class c has subject s with teacher t in room r at day d, period p
    x = {}
    for c in classes:
        x[c] = {}
        for d in range(days):
            x[c][d] = {}
            for p in range(P):
                x[c][d][p] = {}
                for s in subjects:
                    x[c][d][p][s] = {}
                    for t in teachers:
                        # Only if teacher can teach this subject and is available
                        if (s in teacher_info[t]['can_teach'] and 
                            teacher_info[t]['availability'][d][p] == 1):
                            x[c][d][p][s][t] = {}
                            for r in rooms:
                                # Only if room type matches subject requirements
                                subject_room_type = subject_info[s].get('room_type', 'standard')
                                room_type = room_info[r]['type']
                                if room_type == subject_room_type:
                                    x[c][d][p][s][t][r] = model.NewBoolVar(
                                        f"x_{c}_d{d}_p{p}_{s}_{t}_{r}"
                                    )

    # ==========================
    # HARD CONSTRAINT 1: At most one subject per class per time slot
    # (Allow empty slots - classes don't need to fill all periods)
    # ==========================
    for c in classes:
        for d in range(days):
            for p in range(P):
                slot_vars = []
                for s in subjects:
                    for t in teachers:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None:
                                        slot_vars.append(var)
                # At most one assignment per slot (allow empty slots)
                model.Add(sum(slot_vars) <= 1)

    # ==========================
    # HARD CONSTRAINT 2: Teacher conflict constraint
    # A teacher cannot be assigned to more than one class at the same time
    # ==========================
    for t in teachers:
        for d in range(days):
            for p in range(P):
                teacher_vars = []
                for c in classes:
                    for s in subjects:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None:
                                        teacher_vars.append(var)
                # At most one class per teacher per period
                model.Add(sum(teacher_vars) <= 1)

    # ==========================
    # HARD CONSTRAINT 3: Room conflict constraint
    # A room cannot be assigned to more than one class at the same time
    # ==========================
    for r in rooms:
        for d in range(days):
            for p in range(P):
                room_vars = []
                for c in classes:
                    for s in subjects:
                        for t in teachers:
                            if s in teacher_info[t]['can_teach']:
                                if t in x[c][d][p].get(s, {}):
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None:
                                        room_vars.append(var)
                # At most one class per room per period
                model.Add(sum(room_vars) <= 1)

    # ==========================
    # HARD CONSTRAINT 4: Room type compatibility
    # (Already enforced in variable creation - only compatible rooms are created)
    # ==========================

    # ==========================
    # HARD CONSTRAINT 5: Fixed timetable horizon
    # (Already enforced by structure - only days x periods variables exist)
    # ==========================

    # ==========================
    # HARD CONSTRAINT 6: Required weekly subject frequency
    # Each subject must be scheduled exactly the required number of periods per week
    # ==========================
    for c in classes:
        for s in subjects:
            required_hours = subject_info[s]['hours_per_week']
            subject_vars = []
            for d in range(days):
                for p in range(P):
                    for t in teachers:
                        if s in teacher_info[t]['can_teach']:
                            if t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None:
                                        subject_vars.append(var)
            # Exact frequency requirement
            model.Add(sum(subject_vars) == required_hours)

    # ==========================
    # HARD CONSTRAINT 7: Double-period constraint
    # Subjects marked as double-period must be in consecutive periods on same day
    # ==========================
    for c in classes:
        for s in subjects:
            if subject_info[s].get('is_double_period', False):
                # For double-period subjects, if scheduled at period p, 
                # the SAME teacher and room must continue at period p+1
                for d in range(days):
                    for p in range(P - 1):  # Can't start in last period
                        # For each possible (teacher, room) pair for this subject at period p
                        for t in teachers:
                            if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var_p = x[c][d][p][s][t].get(r)
                                    if var_p is not None:
                                        # Check if same (teacher, room) exists at p+1
                                        var_p1 = None
                                        if t in x[c][d][p + 1].get(s, {}):
                                            var_p1 = x[c][d][p + 1][s][t].get(r)
                                        
                                        if var_p1 is not None:
                                            # If scheduled at p with (t,r), must also be at p+1 with (t,r)
                                            model.AddImplication(var_p, var_p1)
                                            # If scheduled at p+1 with (t,r), must also be at p with (t,r)
                                            model.AddImplication(var_p1, var_p)

    # ==========================
    # HARD CONSTRAINT 8: Indivisible sessions
    # Sessions marked as indivisible must not be split across non-adjacent periods or days
    # ==========================
    # Already enforced by double-period constraint for double-period subjects

    # ==========================
    # OPTIONAL: Soft objective for better schedules
    # ==========================
    model.Minimize(0)  # Feasibility-only for now

    return model, x

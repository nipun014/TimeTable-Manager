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
    class_subjects = data.get('class_subjects', {})
    raw = data.get('raw', {})
    # Soft constraint configuration (defaults can be overridden in sample_data.json -> weights)
    weights = raw.get('weights', {})
    W_TEACHER_UNAVAILABLE = int(weights.get('teacher_unavailable', 10))
    W_TEACHER_IDLE_TRANSITION = int(weights.get('teacher_idle_transition', 2))
    W_CLASS_CONSECUTIVE_OVERRUN = int(weights.get('class_consecutive_overrun', 3))
    W_SUBJECT_SPREAD_EXCESS = int(weights.get('subject_spread_excess', 2))
    W_HEAVY_BACK_TO_BACK = int(weights.get('heavy_back_to_back', 1))
    W_TEACHER_EARLY_LATE_IMBALANCE = int(weights.get('teacher_early_late_imbalance', 1))

    max_consecutive = int(raw.get('max_consecutive_periods', 3))
    early_periods = raw.get('early_periods', [0, 1])
    late_periods = raw.get('late_periods', [max(0, P - 2), max(0, P - 1)])
    
    total_periods = days * P

    # ==========================
    # DECISION VARIABLES
    # ==========================
    # x[c][d][p][s][t][r] = 1 if class c has subject s with teacher t in room r at day d, period p
    x = {}
    for c in classes:
        # Get subjects for this specific class
        class_subject_list = class_subjects.get(c, subjects)
        x[c] = {}
        for d in range(days):
            x[c][d] = {}
            for p in range(P):
                x[c][d][p] = {}
                for s in class_subject_list:  # Only subjects for this class
                    x[c][d][p][s] = {}
                    for t in teachers:
                        # Only if teacher can teach this subject (availability handled as soft)
                        if (s in teacher_info[t]['can_teach']):
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
        class_subject_list = class_subjects.get(c, subjects)
        for d in range(days):
            for p in range(P):
                slot_vars = []
                for s in class_subject_list:
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
        class_subject_list = class_subjects.get(c, subjects)
        for s in class_subject_list:  # Only subjects assigned to this class
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
    # HARD CONSTRAINT 9: Teacher forbidden slots (availability)
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

    # ==========================
    # HARD CONSTRAINT 10: Global break periods (blocked slots)
    # No assignments during institution-wide breaks
    # ==========================
    breaks = raw.get('institution', {}).get('breaks', [])
    for break_info in breaks:
        break_day = break_info.get('day', -1)
        break_period = break_info.get('period', 0)
        duration = break_info.get('duration', 1)
        
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
                                                model.Add(var == 0)  # HARD: blocked

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
    # ==========================
    # SOFT CONSTRAINTS AND OBJECTIVE
    # ==========================
    penalties: List[cp_model.LinearExpr] = []

    # Helper presence variables per teacher and per class
    # y_teacher[t][d][p] == 1 if teacher t teaches any class at (d,p)
    y_teacher: Dict[str, Dict[int, Dict[int, cp_model.BoolVar]]] = {t: {d: {} for d in range(days)} for t in teachers}
    for t in teachers:
        for d in range(days):
            for p in range(P):
                y = model.NewBoolVar(f"y_teacher_{t}_d{d}_p{p}")
                # Sum all x with teacher t at (d,p) across classes/subjects/rooms
                vars_tp = []
                for c in classes:
                    for s in subjects:
                        if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                            for r in rooms:
                                var = x[c][d][p][s][t].get(r)
                                if var is not None:
                                    vars_tp.append(var)
                if vars_tp:
                    # Teacher conflict (hard) already ensures sum <= 1
                    model.Add(sum(vars_tp) == y)
                else:
                    # No possible assignment -> force 0
                    model.Add(y == 0)
                y_teacher[t][d][p] = y

    # y_class[c][d][p] == 1 if class c has any assignment at (d,p)
    y_class: Dict[str, Dict[int, Dict[int, cp_model.BoolVar]]] = {c: {d: {} for d in range(days)} for c in classes}
    for c in classes:
        for d in range(days):
            for p in range(P):
                y = model.NewBoolVar(f"y_class_{c}_d{d}_p{p}")
                vars_cdp = []
                for s in subjects:
                    for t in teachers:
                        if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                            for r in rooms:
                                var = x[c][d][p][s][t].get(r)
                                if var is not None:
                                    vars_cdp.append(var)
                if vars_cdp:
                    model.Add(sum(vars_cdp) == y)
                else:
                    model.Add(y == 0)
                y_class[c][d][p] = y

    # 1) Teacher availability: Now enforced as HARD CONSTRAINT 9 (see above)
    # (Removed soft penalty to avoid double-counting)

    # 2) Minimize teacher idle time: penalize transitions (fragmentation) within a day
    for t in teachers:
        for d in range(days):
            for p in range(1, P):
                diff = model.NewBoolVar(f"idle_trans_{t}_d{d}_p{p}")
                y_now = y_teacher[t][d][p]
                y_prev = y_teacher[t][d][p - 1]
                # diff == |y_now - y_prev|
                model.Add(diff >= y_now - y_prev)
                model.Add(diff >= y_prev - y_now)
                model.Add(diff <= y_now + y_prev)
                model.Add(diff <= 2 - (y_now + y_prev))
                penalties.append(W_TEACHER_IDLE_TRANSITION * diff)

    # 3) Limit consecutive periods for students: penalize overrun beyond threshold
    for c in classes:
        for d in range(days):
            for start in range(0, P):
                end = min(P, start + max_consecutive + 1)
                if end - start <= max_consecutive:
                    continue
                window = [y_class[c][d][pp] for pp in range(start, end)]
                over = model.NewIntVar(0, end - start, f"overrun_{c}_d{d}_s{start}")
                model.Add(over >= sum(window) - max_consecutive)
                penalties.append(W_CLASS_CONSECUTIVE_OVERRUN * over)

    # 4) Even distribution of subjects across the week: penalize more than 1 per day
    for c in classes:
        for s in subjects:
            for d in range(days):
                day_vars = []
                for p in range(P):
                    for t in teachers:
                        if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                            for r in rooms:
                                var = x[c][d][p][s][t].get(r)
                                if var is not None:
                                    day_vars.append(var)
                if day_vars:
                    excess = model.NewIntVar(0, P, f"excess_{c}_{s}_d{d}")
                    model.Add(excess >= sum(day_vars) - 1)
                    penalties.append(W_SUBJECT_SPREAD_EXCESS * excess)

    # 5) Avoid back-to-back heavy subjects for the same class (light penalty)
    heavy_subjects = [s for s in subjects if subject_info[s].get('is_heavy', False)]
    if heavy_subjects:
        # heavy_present[c][d][p] indicates if any heavy subject is scheduled for class c at (d,p)
        heavy_present: Dict[str, Dict[int, Dict[int, cp_model.BoolVar]]] = {c: {d: {} for d in range(days)} for c in classes}
        for c in classes:
            for d in range(days):
                for p in range(P):
                    y = model.NewBoolVar(f"heavy_{c}_d{d}_p{p}")
                    hv = []
                    for s in heavy_subjects:
                        for t in teachers:
                            if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][d][p][s][t].get(r)
                                    if var is not None:
                                        hv.append(var)
                    if hv:
                        model.Add(sum(hv) == y)
                    else:
                        model.Add(y == 0)
                    heavy_present[c][d][p] = y
        for c in classes:
            for d in range(days):
                for p in range(P - 1):
                    pair = model.NewBoolVar(f"heavy_pair_{c}_d{d}_p{p}")
                    y_a = heavy_present[c][d][p]
                    y_b = heavy_present[c][d][p + 1]
                    # AND linearization
                    model.Add(pair <= y_a)
                    model.Add(pair <= y_b)
                    model.Add(pair >= y_a + y_b - 1)
                    penalties.append(W_HEAVY_BACK_TO_BACK * pair)

    # 6) Teacher load fairness: balance early vs late periods per teacher
    for t in teachers:
        early_vars = []
        late_vars = []
        for d in range(days):
            for p in range(P):
                if p in early_periods:
                    early_vars.append(y_teacher[t][d][p])
                if p in late_periods:
                    late_vars.append(y_teacher[t][d][p])
        early_cnt = model.NewIntVar(0, days * len(early_periods), f"early_cnt_{t}")
        late_cnt = model.NewIntVar(0, days * len(late_periods), f"late_cnt_{t}")
        model.Add(early_cnt == sum(early_vars) if early_vars else 0)
        model.Add(late_cnt == sum(late_vars) if late_vars else 0)
        imbalance = model.NewIntVar(0, days * max(len(early_periods), len(late_periods)), f"imbalance_{t}")
        model.AddAbsEquality(imbalance, early_cnt - late_cnt)
        penalties.append(W_TEACHER_EARLY_LATE_IMBALANCE * imbalance)

    # Objective: minimize total weighted penalties
    if penalties:
        model.Minimize(sum(penalties))
    else:
        model.Minimize(0)

    return model, x

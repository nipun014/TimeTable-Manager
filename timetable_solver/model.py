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

    x = {}
    for c in classes:
        class_subject_list = class_subjects.get(c, subjects)
        x[c] = {}
        for d in range(days):
            x[c][d] = {}
            for p in range(P):
                x[c][d][p] = {}
                for s in class_subject_list:
                    x[c][d][p][s] = {}
                    for t in teachers:
                        if (s in teacher_info[t]['can_teach']):
                            x[c][d][p][s][t] = {}
                            for r in rooms:
                                subject_room_type = subject_info[s].get('room_type', 'standard')
                                room_type = room_info[r]['type']
                                if room_type == subject_room_type:
                                    x[c][d][p][s][t][r] = model.NewBoolVar(
                                        f"x_{c}_d{d}_p{p}_{s}_{t}_{r}"
                                    )

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
                model.Add(sum(slot_vars) <= 1)

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
                model.Add(sum(teacher_vars) <= 1)

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
                model.Add(sum(room_vars) <= 1)

    for c in classes:
        class_subject_list = class_subjects.get(c, subjects)
        for s in class_subject_list:
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
            model.Add(sum(subject_vars) == required_hours)

    for c in classes:
        for d in range(days):
            for p in range(P):
                for s in subjects:
                    for t in teachers:
                        if s in teacher_info[t]['can_teach']:
                            if int(teacher_info[t]['availability'][d][p]) == 0:
                                if t in x[c][d][p].get(s, {}):
                                    for r in rooms:
                                        var = x[c][d][p][s][t].get(r)
                                        if var is not None:
                                            model.Add(var == 0)

    breaks = raw.get('institution', {}).get('breaks', [])
    for break_info in breaks:
        break_day = break_info.get('day', -1)
        break_period = break_info.get('period', 0)
        duration = break_info.get('duration', 1)
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

    for c in classes:
        for s in subjects:
            if subject_info[s].get('is_double_period', False):
                for d in range(days):
                    for p in range(P - 1):
                        for t in teachers:
                            if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                                for r in rooms:
                                    var_p = x[c][d][p][s][t].get(r)
                                    if var_p is not None:
                                        var_p1 = None
                                        if t in x[c][d][p + 1].get(s, {}):
                                            var_p1 = x[c][d][p + 1][s][t].get(r)
                                        
                                        if var_p1 is not None:
                                            model.AddImplication(var_p, var_p1)
                                            model.AddImplication(var_p1, var_p)

    penalties: List[cp_model.LinearExpr] = []

    y_teacher: Dict[str, Dict[int, Dict[int, cp_model.BoolVar]]] = {t: {d: {} for d in range(days)} for t in teachers}
    for t in teachers:
        for d in range(days):
            for p in range(P):
                y = model.NewBoolVar(f"y_teacher_{t}_d{d}_p{p}")
                vars_tp = []
                for c in classes:
                    for s in subjects:
                        if s in teacher_info[t]['can_teach'] and t in x[c][d][p].get(s, {}):
                            for r in rooms:
                                var = x[c][d][p][s][t].get(r)
                                if var is not None:
                                    vars_tp.append(var)
                if vars_tp:
                    model.Add(sum(vars_tp) == y)
                else:
                    model.Add(y == 0)
                y_teacher[t][d][p] = y

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

    for t in teachers:
        for d in range(days):
            for p in range(1, P):
                diff = model.NewBoolVar(f"idle_trans_{t}_d{d}_p{p}")
                y_now = y_teacher[t][d][p]
                y_prev = y_teacher[t][d][p - 1]
                model.Add(diff >= y_now - y_prev)
                model.Add(diff >= y_prev - y_now)
                model.Add(diff <= y_now + y_prev)
                model.Add(diff <= 2 - (y_now + y_prev))
                penalties.append(W_TEACHER_IDLE_TRANSITION * diff)

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

    heavy_subjects = [s for s in subjects if subject_info[s].get('is_heavy', False)]
    if heavy_subjects:
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
                    model.Add(pair <= y_a)
                    model.Add(pair <= y_b)
                    model.Add(pair >= y_a + y_b - 1)
                    penalties.append(W_HEAVY_BACK_TO_BACK * pair)

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

    if penalties:
        model.Minimize(sum(penalties))
    else:
        model.Minimize(0)

    return model, x

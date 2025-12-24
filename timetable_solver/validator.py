from typing import Dict, List


class ValidationResult:
    def __init__(self):
        self.is_valid = True
        self.violations = []  # List of violation strings
        self.soft_penalty = 0
        self.hard_count = 0
        self.soft_count = 0


def validate_timetable(data: Dict, x, solver) -> ValidationResult:
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
    class_subjects = data.get('class_subjects', {c: subjects for c in classes})
    
    def get_value(var):
        return solver.Value(var) if var is not None else 0
    
    for c in classes:
        class_subj_list = class_subjects.get(c, subjects)
        for d in range(days):
            for p in range(P):
                count = 0
                for s in class_subj_list:
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
    
    for c in classes:
        class_subj_list = class_subjects.get(c, subjects)
        for s in class_subj_list:
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
                                        if get_value(var) == 1:
                                            result.violations.append(
                                                f"HC5: Teacher {t} scheduled in unavailable slot (Day {d+1}, Period {p+1})"
                                            )
                                            result.is_valid = False
    
    for c in classes:
        class_subj_list = class_subjects.get(c, subjects)
        for d in range(days):
            for p in range(P):
                for s in class_subj_list:
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
    
    for c in classes:
        for s in subjects:
            if subject_info[s].get('is_double_period', False):
                for d in range(days):
                    for p in range(P - 1):
                        for t in teachers:
                            if s in teacher_info[t]['can_teach']:
                                if t in x[c][d][p].get(s, {}):
                                    for r in rooms:
                                        var_p = x[c][d][p][s][t].get(r)
                                        if var_p is not None and get_value(var_p) == 1:
                                            var_p1 = None
                                            if t in x[c][d][p+1].get(s, {}):
                                                var_p1 = x[c][d][p+1][s][t].get(r)
                                            if var_p1 is None or get_value(var_p1) != 1:
                                                result.violations.append(
                                                    f"HC7: Double-period {s} for class {c} at Day {d+1} Period {p+1} not continued at Period {p+2} with same teacher/room"
                                                )
                                                result.is_valid = False
    
    result.hard_count = len([v for v in result.violations if v.startswith('HC')])
    return result


def explain_infeasibility(data: Dict) -> List[str]:
    suggestions = []
    
    classes = data['classes']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    teacher_info = data['teacher_info']
    subject_info = data['subject_info']
    room_info = data['room_info']
    days = data['days']
    P = data['periods_per_day']
    
    total_slots = days * P
    
    total_hours_needed = len(classes) * sum(subject_info[s]['hours_per_week'] for s in subjects)
    if total_hours_needed > total_slots * len(teachers):
        suggestions.append(
            f"⚠️  Insufficient teacher capacity: {total_hours_needed} hours needed, "
            f"but only {total_slots * len(teachers)} slot-hours available"
        )
    
    for t in teachers:
        available_slots = sum(
            int(teacher_info[t]['availability'][d][p])
            for d in range(days)
            for p in range(P)
        )
        if available_slots == 0:
            suggestions.append(f"⚠️  Teacher {t} has zero available time slots")
    
    room_types = {}
    for r in rooms:
        rtype = room_info[r]['type']
        room_types[rtype] = room_types.get(rtype, 0) + 1
    
    subject_room_needs = {}
    for s in subjects:
        rtype = subject_info[s].get('room_type', 'standard')
        subject_room_needs[rtype] = subject_room_needs.get(rtype, 0) + 1
    
    for rtype, need_count in subject_room_needs.items():
        if room_types.get(rtype, 0) == 0:
            suggestions.append(f"⚠️  {need_count} subject(s) need '{rtype}' rooms but 0 available")
    
    for s in subjects:
        qualified_teachers = [t for t in teachers if s in teacher_info[t]['can_teach']]
        if not qualified_teachers:
            suggestions.append(f"⚠️  Subject {s} has NO qualified teachers")
    
    return suggestions


class PreValidationResult:
    def __init__(self):
        self.is_valid = True
        self.errors = []      # Critical issues that prevent solving
        self.warnings = []    # Non-critical issues that may affect quality
        self.info = []        # Informational messages


def pre_validate_input(data: Dict) -> PreValidationResult:
    result = PreValidationResult()
    
    classes = data['classes']
    days = data['days']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    teacher_info = data['teacher_info']
    room_info = data['room_info']
    subject_info = data['subject_info']
    class_subjects = data.get('class_subjects', {c: subjects for c in classes})
    
    total_slots = days * P
    blocked_slots = data.get('raw', {}).get('institution', {}).get('blocked_slots', [])
    available_slots_per_class = total_slots - len(blocked_slots)
    
    result.info.append(f"[INFO] Total slots per class: {total_slots} ({days} days x {P} periods)")
    result.info.append(f"[INFO] Blocked slots: {len(blocked_slots)}")
    result.info.append(f"[INFO] Available slots: {available_slots_per_class}")
    
    for c in classes:
        class_subj_list = class_subjects.get(c, subjects)
        total_required_hours = sum(
            subject_info[s]['hours_per_week'] 
            for s in class_subj_list
        )
        
        if total_required_hours > available_slots_per_class:
            result.errors.append(
                f"[ERROR] Class {c}: Required {total_required_hours} hours but only "
                f"{available_slots_per_class} slots available (exceeds by "
                f"{total_required_hours - available_slots_per_class})"
            )
            result.is_valid = False
        elif total_required_hours > available_slots_per_class * 0.95:
            result.warnings.append(
                f"[WARN] Class {c}: Very tight schedule - {total_required_hours} hours in "
                f"{available_slots_per_class} slots ({total_required_hours/available_slots_per_class*100:.1f}% utilization)"
            )
        
        result.info.append(f"   Class {c}: {total_required_hours}/{available_slots_per_class} hours")
    
    for s in subjects:
        qualified_teachers = [t for t in teachers if s in teacher_info[t]['can_teach']]
        if not qualified_teachers:
            result.errors.append(
                f"[ERROR] Subject '{s}' has NO qualified teachers - cannot be scheduled"
            )
            result.is_valid = False
    
    room_types = {}
    for r in rooms:
        rtype = room_info[r]['type']
        room_types[rtype] = room_types.get(rtype, 0) + 1
    
    subject_room_needs = {}
    for s in subjects:
        rtype = subject_info[s].get('room_type', 'standard')
        subject_room_needs[rtype] = subject_room_needs.get(rtype, 0) + 1
    
    for rtype, need_count in subject_room_needs.items():
        if room_types.get(rtype, 0) == 0:
            result.errors.append(
                f"[ERROR] {need_count} subject(s) require '{rtype}' rooms but NONE available"
            )
            result.is_valid = False
    
    result.info.append(f"[INFO] Room types: {room_types}")
    result.info.append(f"[INFO] Subject room needs: {subject_room_needs}")
    
    total_teaching_demand = 0
    for c in classes:
        class_subj_list = class_subjects.get(c, subjects)
        for s in class_subj_list:
            total_teaching_demand += subject_info[s]['hours_per_week']
    
    total_teacher_availability = 0
    teacher_availability_map = {}
    for t in teachers:
        avail_matrix = teacher_info[t].get('availability', None)
        if avail_matrix is None:
            teacher_slots = total_slots - len(blocked_slots)
        else:
            teacher_slots = sum(sum(day) for day in avail_matrix)
        
        total_teacher_availability += teacher_slots
        teacher_availability_map[t] = teacher_slots
    
    result.info.append(f"[INFO] Total teaching demand: {total_teaching_demand} hours")
    result.info.append(f"[INFO] Total teacher availability: {total_teacher_availability} slots")
    
    if total_teaching_demand > total_teacher_availability:
        result.errors.append(
            f"[ERROR] INSUFFICIENT TEACHER CAPACITY: Need {total_teaching_demand} hours but "
            f"only {total_teacher_availability} teacher-slots available "
            f"(shortage: {total_teaching_demand - total_teacher_availability})"
        )
        result.is_valid = False
    elif total_teaching_demand > total_teacher_availability * 0.90:
        result.warnings.append(
            f"[WARN] Teacher capacity is very tight: {total_teaching_demand} demand vs "
            f"{total_teacher_availability} availability ({total_teaching_demand/total_teacher_availability*100:.1f}% utilization)"
        )
    
    for t in teachers:
        teacher_can_teach = teacher_info[t]['can_teach']
        teacher_demand = 0
        
        max_demand = 0
        for s in teacher_can_teach:
            classes_needing_subject = [c for c in classes if s in class_subjects.get(c, subjects)]
            max_demand += len(classes_needing_subject) * subject_info[s]['hours_per_week']
        
        teacher_capacity = teacher_availability_map[t]
        
        if max_demand > teacher_capacity:
            if max_demand > teacher_capacity * 2:
                result.warnings.append(
                    f"[WARN] Teacher {t}: Maximum possible demand {max_demand} hours >> capacity {teacher_capacity} slots "
                    f"(may be over-utilized if assigned many classes)"
                )
    
    max_concurrent_classes = len(classes)
    total_rooms = len(rooms)
    
    if max_concurrent_classes > total_rooms:
        result.errors.append(
            f"[ERROR] ROOM SHORTAGE: {max_concurrent_classes} classes but only {total_rooms} rooms "
            f"(need {max_concurrent_classes - total_rooms} more rooms)"
        )
        result.is_valid = False
    
    lab_subjects = [s for s in subjects if subject_info[s].get('room_type') in ['lab', 'computer']]
    lab_rooms = [r for r in rooms if room_info[r]['type'] in ['lab', 'computer']]
    
    if lab_subjects and not lab_rooms:
        result.errors.append(
            f"[ERROR] Lab subjects exist but NO lab/computer rooms available"
        )
        result.is_valid = False
    elif len(lab_subjects) > len(lab_rooms) * days * P * 0.3:
        result.warnings.append(
            f"[WARN] Lab room capacity may be tight: {len(lab_subjects)} lab subjects, "
            f"{len(lab_rooms)} lab rooms"
        )
    
    if len(blocked_slots) > 0:
        for c in classes:
            class_subj_list = class_subjects.get(c, subjects)
            total_required = sum(subject_info[s]['hours_per_week'] for s in class_subj_list)
            
            if total_required > (total_slots - len(blocked_slots)) * 0.8:
                result.warnings.append(
                    f"[WARN] Class {c}: Blocked slots reduce flexibility - may cause infeasibility"
                )
    
    for t in teachers:
        avail_matrix = teacher_info[t].get('availability', None)
        if avail_matrix is not None:
            unavailable_slots = 0
            for day_avail in avail_matrix:
                unavailable_slots += sum(1 for slot in day_avail if slot == 0)
            
            if unavailable_slots > total_slots * 0.5:
                result.warnings.append(
                    f"[WARN] Teacher {t}: Low availability - {unavailable_slots}/{total_slots} slots unavailable "
                    f"({unavailable_slots/total_slots*100:.1f}% unavailable)"
                )
    
    double_period_subjects = [s for s in subjects if subject_info[s].get('is_double_period', False)]
    if double_period_subjects:
        result.warnings.append(
            f"[WARN] {len(double_period_subjects)} subject(s) require consecutive periods - "
            f"may reduce scheduling flexibility"
        )
    
    return result

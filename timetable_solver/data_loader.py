from typing import Dict, List


def _reshape(rows, days: int, periods: int) -> List[List[int]]:
    """Force an availability matrix to exactly days x periods. Missing = available."""
    out = [list(r)[:periods] + [1] * max(0, periods - len(r)) for r in (rows or [])[:days]]
    out += [[1] * periods for _ in range(days - len(out))]
    return out


def prepare_data(data: Dict) -> Dict:
    classes = data['classes']
    days = data.get('days', 5)
    periods_per_day = data.get('periods_per_day', 6)
    subjects = list(data['subjects'].keys())
    teachers = list(data['teachers'].keys())
    rooms = list(data.get('rooms', {}).keys())

    teacher_info = data['teachers']
    room_info = data.get('rooms', {})
    subject_info = data['subjects']
    class_subjects = data.get('class_subjects', {c: subjects for c in classes})

    # model.py indexes availability[d][p] and silently ignores extra columns, while
    # pre_validate_input sums the raw rows — a mismatched grid inflates reported
    # teacher capacity. Normalize once here so every consumer sees the same shape.
    normalizations = []
    for t in teachers:
        rows = teacher_info[t].get('availability')
        fixed = _reshape(rows, days, periods_per_day)
        if rows != fixed:
            shape = f"{len(rows)}x{len(rows[0])}" if rows else "missing"
            normalizations.append(
                f"[WARN] Teacher {t}: availability was {shape}, "
                f"reshaped to {days}x{periods_per_day} (padded slots count as available)"
            )
        teacher_info[t]['availability'] = fixed

    return {
        'classes': classes,
        'days': days,
        'periods_per_day': periods_per_day,
        'subjects': subjects,
        'teachers': teachers,
        'rooms': rooms,
        'teacher_info': teacher_info,
        'room_info': room_info,
        'subject_info': subject_info,
        'class_subjects': class_subjects,
        'normalizations': normalizations,
        'raw': data,
    }

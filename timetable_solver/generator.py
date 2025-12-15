"""
generator.py

Utility to convert solver output into JSON / CSV / other formats. Minimal example
returns a dict representation.
"""

def extract_solution(data, x, solver):
    classes = data['classes']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']

    out = {c: [] for c in classes}
    for c in classes:
        for p in range(P):
            entry = {'period': p+1, 'subject': None, 'teacher': None}
            for s in subjects:
                for t in teachers:
                    if s in data['teacher_info'][t]['can_teach']:
                        var = x[c][p][s].get(t)
                        if var is not None and solver.Value(var) == 1:
                            entry['subject'] = s
                            entry['teacher'] = t
            out[c].append(entry)
    return out

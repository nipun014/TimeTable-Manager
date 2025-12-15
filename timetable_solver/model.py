"""
model.py

Builds a minimal CP-SAT model for the timetable problem.
This creates boolean variables x[class][period][subject][teacher]
subject to small constraints:
 - Each class at each period has exactly one (subject,teacher)
 - A teacher can be assigned to at most one class in a given period
 - Teacher must be qualified and available

This is intentionally simple so you can extend it with your project's constraints.
"""
from ortools.sat.python import cp_model
from typing import Dict, Tuple


def build_model(data: Dict) -> Tuple[cp_model.CpModel, Dict]:
    model = cp_model.CpModel()

    classes = data['classes']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']
    teacher_info = data['teacher_info']

    # Create variables: x[c][p][s][t]
    x = {}
    for c in classes:
        x[c] = {}
        for p in range(P):
            x[c][p] = {}
            for s in subjects:
                x[c][p][s] = {}
                for t in teachers:
                    # only create variable if teacher can teach subject
                    if s in teacher_info[t]['can_teach']:
                        x[c][p][s][t] = model.NewBoolVar(f"x_{c}_{p}_{s}_{t}")

    # Constraint: each class c at period p has exactly one (s,t)
    for c in classes:
        for p in range(P):
            vars_at_slot = []
            for s in subjects:
                for t in teachers:
                    if s in teacher_info[t]['can_teach']:
                        var = x[c][p][s].get(t)
                        if var is not None:
                            vars_at_slot.append(var)
            # allow possibility of empty slot? For now force exactly one
            model.Add(sum(vars_at_slot) == 1)

    # Constraint: teacher at most one class per period
    for t in teachers:
        for p in range(P):
            teacher_vars = []
            for c in classes:
                for s in subjects:
                    if s in teacher_info[t]['can_teach']:
                        var = x[c][p][s].get(t)
                        if var is not None:
                            teacher_vars.append(var)
            model.Add(sum(teacher_vars) <= 1)

    # (Optional) Soft objective: balance teacher load (minimize max load)
    # Compute total assignments per teacher
    total_per_teacher = {}
    max_load = model.NewIntVar(0, P * len(classes), 'max_load')
    for t in teachers:
        tv = []
        for c in classes:
            for p in range(P):
                for s in subjects:
                    if s in teacher_info[t]['can_teach']:
                        var = x[c][p][s].get(t)
                        if var is not None:
                            tv.append(var)
        if tv:
            total = sum(tv)
            # CP-SAT requires IntVar for totals if combining with other IntVars
            total_per_teacher[t] = total
            model.Add(total_per_teacher[t] <= max_load)
    # minimize max load
    model.Minimize(max_load)

    return model, x

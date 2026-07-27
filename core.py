"""Solve + render helpers. No UI calls, so this is importable and testable."""
import html
import json

import pandas as pd
import streamlit as st
from ortools.sat.python import cp_model

from timetable_solver.data_loader import prepare_data
from timetable_solver.generator import build_solution
from timetable_solver.model import build_model
from timetable_solver.validator import (
    explain_infeasibility,
    pre_validate_input,
    validate_timetable,
)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PALETTE = [210, 145, 32, 275, 0, 190, 95, 315, 250, 55, 170, 290]


@st.cache_data(show_spinner=False)
def solve(raw_json: str, time_limit: int, seed: int) -> dict:
    """Run CP-SAT. Cached on the exact input + settings, so reruns are free."""
    data = prepare_data(json.loads(raw_json))
    pre = pre_validate_input(data)
    if pre.errors:
        return {"status": "INVALID", "errors": pre.errors, "warnings": pre.warnings}

    model, x = build_model(data)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = seed

    res = solver.Solve(model)
    if res not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": solver.StatusName(res),
            "errors": explain_infeasibility(data),
            "warnings": pre.warnings,
        }

    report = validate_timetable(data, x, solver)
    return {
        "status": solver.StatusName(res),
        "solution": build_solution(data, x, solver),
        "objective": solver.ObjectiveValue(),
        "runtime": solver.WallTime(),
        "violations": report.violations,
        "warnings": pre.warnings,
    }


def day_label(index: int) -> str:
    return DAY_NAMES[index] if index < len(DAY_NAMES) else f"D{index + 1}"


def stat(value, label, tone="") -> str:
    return f'<div class="stat {tone}"><div class="v">{value}</div><div class="k">{label}</div></div>'


def grid(timetable: list, key_a: str, key_b: str) -> str:
    """Render a days x periods grid. Each slot shows key_a big, key_b as subtitle."""
    periods = len(timetable[0])
    head = "".join(f"<th>P{p + 1}</th>" for p in range(periods))
    rows = []
    for d, day in enumerate(timetable):
        cells = []
        for slot in day:
            title = slot.get(key_a)
            if not title:
                cells.append('<td><div class="cell free"><b>Free</b></div></td>')
                continue
            h = PALETTE[sum(map(ord, str(title))) % len(PALETTE)]  # stable across restarts
            sub = " · ".join(str(slot[k]) for k in key_b.split(",") if slot.get(k))
            # full colors inlined, not CSS vars — sanitizers keep plain declarations
            style = (
                f"background:hsl({h},55%,16%);border:1px solid hsl({h},55%,30%)"
            )
            cells.append(
                f'<td><div class="cell" style="{style}">'
                f'<b style="color:hsl({h},80%,78%)">{html.escape(str(title))}</b>'
                f"<span>{html.escape(sub)}</span></div></td>"
            )
        rows.append(f'<tr><th class="day">{day_label(d)}</th>{"".join(cells)}</tr>')
    return (
        f'<table class="tt"><thead><tr><th class="day"></th>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def to_dataframe(solution: dict) -> pd.DataFrame:
    rows = [
        {
            "Class": cls,
            "Day": day_label(slot["day"] - 1),
            "Period": f"P{slot['period']}",
            "Subject": slot["subject"] or "Free",
            "Teacher": slot["teacher"] or "-",
            "Room": slot["room"] or "-",
        }
        for cls, table in solution["class_timetables"].items()
        for day in table
        for slot in day
    ]
    return pd.DataFrame(rows)

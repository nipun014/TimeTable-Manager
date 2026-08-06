"""Solve entry point. UI-free, so it is importable from the API and testable."""
import json

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


def day_label(index: int) -> str:
    return DAY_NAMES[index] if index < len(DAY_NAMES) else f"D{index + 1}"


def solve(raw_json: str, time_limit: int, seed: int) -> dict:
    """Run CP-SAT on a raw input JSON string."""
    data = prepare_data(json.loads(raw_json))
    pre = pre_validate_input(data)
    warnings = data['normalizations'] + pre.warnings
    if pre.errors:
        return {"status": "INVALID", "errors": pre.errors, "warnings": warnings}

    model, x = build_model(data)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = int(
        data['raw'].get('solver_config', {}).get('num_workers') or 8
    )
    solver.parameters.random_seed = seed

    res = solver.Solve(model)
    if res not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": solver.StatusName(res),
            "errors": explain_infeasibility(data),
            "warnings": warnings,
        }

    report = validate_timetable(data, x, solver)
    return {
        "status": solver.StatusName(res),
        "solution": build_solution(data, x, solver),
        "objective": solver.ObjectiveValue(),
        "runtime": solver.WallTime(),
        "violations": report.violations,
        "warnings": warnings,
    }

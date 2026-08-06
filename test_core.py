"""Smoke tests for the CP-SAT solve path."""
import json
from pathlib import Path

from core import solve

ROOT = Path(__file__).parent


def test_solve_simple_sample():
    raw = (ROOT / "simple_sample.json").read_text(encoding="utf-8")
    result = solve(raw, 30, 42)

    assert "solution" in result, f"no solution: {result.get('errors')}"
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert not result["violations"], result["violations"][:5]

    data = json.loads(raw)
    tables = result["solution"]["class_timetables"]
    assert set(tables) == set(data["classes"])

    # every class gets a full days x periods grid, free slots included
    for table in tables.values():
        assert len(table) == data["days"]
        assert all(len(day) == data["periods_per_day"] for day in table)


def test_three_period_lab_block():
    """KTU labs must land on N consecutive periods, same teacher and room."""
    tiny = {
        "days": 1,
        "periods_per_day": 6,
        "classes": ["C1"],
        "class_subjects": {"C1": ["THEORY", "LAB"]},
        "subjects": {
            "THEORY": {"hours_per_week": 2, "room_type": "standard", "block_size": 1},
            "LAB": {"hours_per_week": 3, "room_type": "lab", "block_size": 3},
        },
        "teachers": {"T1": {"can_teach": ["THEORY", "LAB"], "availability": [[1] * 6]}},
        "rooms": {"R1": {"type": "standard"}, "L1": {"type": "lab"}},
    }
    result = solve(json.dumps(tiny), 20, 1)
    assert "solution" in result, result.get("errors")
    assert not result["violations"], result["violations"]

    day = result["solution"]["class_timetables"]["C1"][0]
    lab = [p for p, slot in enumerate(day) if slot["subject"] == "LAB"]
    assert len(lab) == 3, f"lab got {len(lab)} periods, want 3"
    assert lab == list(range(lab[0], lab[0] + 3)), f"lab not consecutive: {lab}"
    assert len({(day[p]["teacher"], day[p]["room"]) for p in lab}) == 1, "teacher/room changed"
    assert day[lab[0]]["room"] == "L1"


def test_block_size_must_divide_hours():
    """4 hours of a 3-period lab is impossible — say so instead of timing out."""
    bad = {
        "days": 5,
        "periods_per_day": 6,
        "classes": ["C1"],
        "class_subjects": {"C1": ["LAB"]},
        "subjects": {"LAB": {"hours_per_week": 4, "room_type": "lab", "block_size": 3}},
        "teachers": {"T1": {"can_teach": ["LAB"], "availability": [[1] * 6] * 5}},
        "rooms": {"L1": {"type": "lab"}},
    }
    result = solve(json.dumps(bad), 5, 1)
    assert result["status"] == "INVALID"
    assert any("multiple of block_size" in e for e in result["errors"]), result["errors"]


def test_availability_grid_is_reshaped():
    """A grid that disagrees with days/periods is fixed and reported, not ignored."""
    raw = {
        "days": 2,
        "periods_per_day": 3,
        "classes": ["C1"],
        "class_subjects": {"C1": ["M"]},
        "subjects": {"M": {"hours_per_week": 2, "room_type": "standard"}},
        "teachers": {"T1": {"can_teach": ["M"], "availability": [[1, 1, 1, 1]]}},
        "rooms": {"R1": {"type": "standard"}},
    }
    result = solve(json.dumps(raw), 10, 1)
    assert "solution" in result, result.get("errors")
    assert any("reshaped to 2x3" in w for w in result["warnings"]), result["warnings"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")

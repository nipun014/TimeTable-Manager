"""Smoke test: the app's solve + render path on the simple sample."""
import json
from pathlib import Path

from core import grid, solve, to_dataframe


def test_solve_and_render():
    raw = (Path(__file__).parent / "simple_sample.json").read_text()
    result = solve.__wrapped__(raw, 30, 42)  # bypass st.cache_data

    assert "solution" in result, f"no solution: {result.get('errors')}"
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert not result["violations"], result["violations"][:5]

    data = json.loads(raw)
    tables = result["solution"]["class_timetables"]
    assert set(tables) == set(data["classes"])

    # every class gets a days x periods grid
    for table in tables.values():
        assert len(table) == data["days"]
        assert all(len(day) == data["periods_per_day"] for day in table)

    markup = grid(tables[data["classes"][0]], "subject", "teacher,room")
    assert markup.count("<td>") == data["days"] * data["periods_per_day"]
    assert markup.count("cell free") == sum(
        1 for day in tables[data["classes"][0]] for s in day if not s["subject"]
    )

    df = to_dataframe(result["solution"])
    assert len(df) == len(data["classes"]) * data["days"] * data["periods_per_day"]
    assert list(df.columns) == ["Class", "Day", "Period", "Subject", "Teacher", "Room"]


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
        "teachers": {
            "T1": {"can_teach": ["THEORY", "LAB"], "availability": [[1] * 6]},
        },
        "rooms": {"R1": {"type": "standard"}, "L1": {"type": "lab"}},
    }
    result = solve.__wrapped__(json.dumps(tiny), 20, 1)
    assert "solution" in result, result.get("errors")
    assert not result["violations"], result["violations"]

    day = result["solution"]["class_timetables"]["C1"][0]
    lab = [p for p, slot in enumerate(day) if slot["subject"] == "LAB"]
    assert len(lab) == 3, f"lab got {len(lab)} periods, want 3"
    assert lab == list(range(lab[0], lab[0] + 3)), f"lab not consecutive: {lab}"
    assert len({(day[p]["teacher"], day[p]["room"]) for p in lab}) == 1, "teacher/room changed"
    assert day[lab[0]]["room"] == "L1"


def test_markdown_not_indented():
    """4-space-indented lines become code blocks: CSS/HTML would print, not render."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=180)
    at.run()
    check_markdown(at)

    # and again on the results page, where most of the raw HTML lives
    at.selectbox[0].select("Simple (2 classes)").run()
    at.button[0].click().run()          # Load sample
    at.button[0].click().run()          # Generate timetable
    assert not at.exception, at.exception
    assert len(at.tabs) == 4
    check_markdown(at)


def check_markdown(at):
    for md in at.markdown:
        bad = [
            line for line in md.value.splitlines()
            if line.startswith("    ") and line.strip()
        ]
        assert not bad, f"indented markdown renders as a code block: {bad[0]!r}"


if __name__ == "__main__":
    test_solve_and_render()
    test_three_period_lab_block()
    test_markdown_not_indented()
    print("ok")

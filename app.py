import html
import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core import grid, solve, stat, to_dataframe

st.set_page_config(page_title="EduSchedule", page_icon="🗓️", layout="wide")

ROOT = Path(__file__).parent
SAMPLES = {
    "Simple (2 classes)": ROOT / "simple_sample.json",
    "KTU S3+S5 (hard, 3-period labs)": ROOT / "ktu_sample.json",
    "Department (20 classes)": ROOT / "timetable_solver" / "sample_data.json",
    "Hard (12 classes, tight)": ROOT / "hard_sample.json",
    "Competitive (9 classes)": ROOT / "competitive_example.json",
}
WEIGHT_LABELS = {
    "teacher_unavailable": "Respect teacher availability",
    "teacher_idle_transition": "Avoid teacher gaps",
    "class_consecutive_overrun": "Limit consecutive periods",
    "subject_spread_excess": "Spread subjects across week",
    "heavy_back_to_back": "Avoid heavy back-to-back",
    "teacher_early_late_imbalance": "Balance early/late slots",
}

# NOTE: keep this at column 0 — markdown turns 4-space-indented lines into a
# code block, which prints the stylesheet on the page instead of applying it.
st.markdown(
    """
<style>
.block-container {padding-top: 2.5rem; max-width: 1400px;}
h1, h2, h3 {letter-spacing: -0.02em;}
.hero {padding: 1rem 0 0.5rem;}
.hero h1 {font-size: 2.6rem; margin: 0;}
.hero p {color: #98a2b8; font-size: 1.05rem; margin: .4rem 0 0;}
.stats {display: flex; gap: .75rem; flex-wrap: wrap; margin: .5rem 0 1.25rem;}
.stat {flex: 1 1 120px; background: #171a23; border: 1px solid #262b38; border-radius: 12px; padding: .85rem 1rem;}
.stat .v {font-size: 1.6rem; font-weight: 650; line-height: 1.1;}
.stat .k {color: #98a2b8; font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; margin-top: .2rem;}
.stat.ok .v {color: #4ade80;}
.stat.warn .v {color: #fbbf24;}
.stat.bad .v {color: #f87171;}
.tt {width: 100%; border-collapse: separate; border-spacing: 4px; table-layout: fixed;}
.tt th {color: #98a2b8; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; padding: .3rem;}
.tt th.day {text-align: right; width: 48px; padding-right: .6rem;}
.tt td {padding: 0;}
.cell {border-radius: 10px; padding: .5rem .6rem; min-height: 62px;}
.cell b {display: block; font-size: .85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.cell span {font-size: .72rem; color: #8b94a8;}
.cell.free {background: #12141b; border: 1px dashed #262b38;}
.cell.free b {color: #4b5266; font-weight: 400;}
</style>
""",
    unsafe_allow_html=True,
)


def view(title: str, tables: dict, key_a: str, key_b: str):
    if not tables:
        st.info(f"No {title.lower()} data in this dataset.")
        return
    pick = st.selectbox(title, list(tables), key=f"pick_{title}")
    st.markdown(grid(tables[pick], key_a, key_b), unsafe_allow_html=True)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 🗓️ EduSchedule")
    st.caption("CP-SAT timetable generator")

    uploaded = st.file_uploader("Upload timetable JSON", type=["json"])
    if uploaded:
        try:
            st.session_state.data = json.load(uploaded)
            st.session_state.source = uploaded.name
        except json.JSONDecodeError as ex:
            st.error(f"Not valid JSON: {ex}")

    sample = st.selectbox("…or load a sample", ["—"] + list(SAMPLES))
    if sample != "—" and st.button("Load sample", width='stretch'):
        st.session_state.data = json.loads(SAMPLES[sample].read_text())
        st.session_state.source = sample

    st.divider()
    time_limit = st.slider("Solver time limit (s)", 5, 180, 60, step=5)
    seed = st.number_input("Random seed", value=42, step=1)

data = st.session_state.get("data")

# ---------------------------------------------------------------- landing
if not data:
    st.markdown(
        '<div class="hero"><h1>Build a conflict-free timetable</h1>'
        "<p>Upload your institution's JSON or load a sample to get started. "
        "Constraints are solved with Google OR-Tools CP-SAT.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "**What the JSON needs**\n\n"
        "- `classes`, `days`, `periods_per_day`\n"
        "- `subjects` — hours per week, room type, whether it's a heavy subject\n"
        "- `teachers` — what each can teach, plus their availability grid\n"
        "- `rooms` — type and capacity\n"
        "- `class_subjects` — which subjects each class takes\n"
    )
    with st.expander("Peek at a sample file"):
        st.json(json.loads(SAMPLES["Simple (2 classes)"].read_text()), expanded=False)
    st.stop()

# ---------------------------------------------------------------- setup
st.markdown(
    f'<div class="hero"><h1>{html.escape(str(data.get("institution", "EduSchedule")))}</h1>'
    f'<p>{html.escape(str(st.session_state.get("source", "uploaded file")))}</p></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="stats">'
    + stat(len(data.get("classes", [])), "Classes")
    + stat(len(data.get("teachers", {})), "Teachers")
    + stat(len(data.get("subjects", {})), "Subjects")
    + stat(len(data.get("rooms", {})), "Rooms")
    + stat(f'{data.get("days", 0)}×{data.get("periods_per_day", 0)}', "Slots / week")
    + "</div>",
    unsafe_allow_html=True,
)

with st.expander("⚙️ Constraints — tune how the solver trades off soft rules"):
    st.caption("Higher weight = the solver tries harder not to break that rule.")
    weights = dict(data.get("weights", {}))
    cols = st.columns(2)
    for i, (key, label) in enumerate(WEIGHT_LABELS.items()):
        weights[key] = cols[i % 2].slider(label, 0, 20, int(weights.get(key, 1)), key=f"w_{key}")
    data["weights"] = weights
    data["max_consecutive_periods"] = st.slider(
        "Max consecutive periods of one subject",
        1, 8, int(data.get("max_consecutive_periods", 3)),
    )

raw_json = json.dumps(data, sort_keys=True)
if st.button("⚡ Generate timetable", type="primary", width='stretch'):
    with st.spinner(f"Solving — up to {time_limit}s…"):
        st.session_state.result = solve(raw_json, time_limit, int(seed))
    st.session_state.result_for = raw_json

result = st.session_state.get("result")
if not result:
    st.stop()

if st.session_state.get("result_for") != raw_json:
    st.warning("Inputs changed since this run — generate again to refresh.")

# ---------------------------------------------------------------- results
for msg in result.get("warnings", []):
    st.warning(msg)

if "solution" not in result:
    if result["status"] == "UNKNOWN":
        st.error("Ran out of time before finding a valid timetable.")
        st.info(
            "The problem isn't proven impossible — the solver just needs longer. "
            "Raise the time limit in the sidebar, try a different seed, or relax constraints."
        )
    else:
        st.error(f"No timetable found — solver status: {result['status']}")
    for msg in result.get("errors", []):
        st.markdown(f"- {msg}")
    st.stop()

solution = result["solution"]
violations = result["violations"]
free = sum(
    1
    for table in solution["class_timetables"].values()
    for day in table
    for slot in day
    if not slot["subject"]
)

st.markdown(
    '<div class="stats">'
    + stat(result["status"].title(), "Status", "ok")
    + stat(len(violations), "Violations", "ok" if not violations else "bad")
    + stat(int(result["objective"]), "Penalty score", "warn" if result["objective"] else "ok")
    + stat(free, "Free slots")
    + stat(f'{result["runtime"]:.1f}s', "Solve time")
    + "</div>",
    unsafe_allow_html=True,
)

if violations:
    with st.expander(f"❌ {len(violations)} constraint violations", expanded=True):
        for v in violations[:25]:
            st.markdown(f"- {v}")
        if len(violations) > 25:
            st.caption(f"…and {len(violations) - 25} more")

tab_class, tab_teacher, tab_room, tab_export = st.tabs(
    ["Classes", "Teachers", "Rooms", "Export"]
)
with tab_class:
    view("Class", solution["class_timetables"], "subject", "teacher,room")
with tab_teacher:
    view("Teacher", solution["teacher_timetables"], "subject", "class,room")
with tab_room:
    view("Room", solution["room_utilization"], "subject", "class,teacher")

with tab_export:
    df = to_dataframe(solution)
    st.dataframe(df, width='stretch', height=360, hide_index=True)

    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "⬇ CSV", df.to_csv(index=False).encode(), "timetable.csv", "text/csv",
        width='stretch',
    )
    c2.download_button(
        "⬇ JSON", json.dumps(solution, indent=2).encode(), "solution.json",
        "application/json", width='stretch',
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Timetable")
    c3.download_button(
        "⬇ Excel", buffer.getvalue(), "timetable.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width='stretch',
    )

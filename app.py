import streamlit as st
import json
import pandas as pd
from timetable_solver import model, solver, data_loader
from timetable_solver.input_parser import parse_text, normalize
from ortools.sat.python import cp_model

# Helper functions to build DataFrames for teachers and rooms
def build_teacher_table(teacher, data, x, solver):
    days = data['days']
    P = data['periods_per_day']
    classes = data['classes']
    subjects = data['subjects']
    rooms = data['rooms']

    table_data = []
    for d in range(days):
        for p in range(P):
            row = {'Day': f"Day {d+1}", 'Period': f"P{p+1}"}
            found = False
            for c in classes:
                for s in subjects:
                    if s in data['teacher_info'][teacher]['can_teach']:
                        if teacher in x[c][d][p].get(s, {}):
                            for r in rooms:
                                var = x[c][d][p][s][teacher].get(r)
                                if var is not None and solver.Value(var) == 1:
                                    row['Class'] = c
                                    row['Subject'] = s
                                    row['Room'] = r
                                    found = True
                                    break
                        if found:
                            break
                if found:
                    break
            if not found:
                row['Class'] = '-'
                row['Subject'] = 'Free'
                row['Room'] = '-'
            table_data.append(row)
    return pd.DataFrame(table_data)

def build_room_table(room, data, x, solver):
    days = data['days']
    P = data['periods_per_day']
    classes = data['classes']
    subjects = data['subjects']
    teachers = data['teachers']

    table_data = []
    for d in range(days):
        for p in range(P):
            row = {'Day': f"Day {d+1}", 'Period': f"P{p+1}"}
            found = False
            for c in classes:
                for s in subjects:
                    for t in teachers:
                        if s in data['teacher_info'][t]['can_teach']:
                            # Guard against subjects not present for this class/slot
                            if t in x[c][d][p].get(s, {}):
                                var = x[c][d][p][s][t].get(room)
                                if var is not None and solver.Value(var) == 1:
                                    row['Class'] = c
                                    row['Subject'] = s
                                    row['Teacher'] = t
                                    found = True
                                    break
                    if found:
                        break
                if found:
                    break
            if not found:
                row['Class'] = '-'
                row['Subject'] = 'Free'
                row['Teacher'] = '-'
            table_data.append(row)
    return pd.DataFrame(table_data)

st.title("University Timetable Generator")

with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload config (JSON/YAML/TXT)", type=["json", "yaml", "yml", "txt"])
    pasted_text = st.text_area("Or paste config (JSON/YAML)")
    max_time = st.number_input("Max Time (seconds)", value=60, min_value=1)
    num_workers = st.number_input("Number of Workers", value=8, min_value=1)

if st.button("Generate Timetable"):
    # Load data
    if uploaded_file is not None:
        text = uploaded_file.read().decode("utf-8")
        raw = parse_text(text)
        data = normalize(raw)
    elif pasted_text.strip():
        raw = parse_text(pasted_text)
        data = normalize(raw)
    else:
        data = data_loader.load_data()

    # Build model
    model_obj, x = model.build_model(data)

    # Solve
    solver_obj = cp_model.CpSolver()
    solver_obj.parameters.max_time_in_seconds = max_time
    solver_obj.parameters.num_search_workers = num_workers

    status = solver_obj.Solve(model_obj)

    # Store in session state
    st.session_state['status'] = status
    st.session_state['solver'] = solver_obj
    st.session_state['x'] = x
    st.session_state['data'] = data
    st.session_state['model'] = model_obj

    st.rerun()  # To update the display

if 'status' in st.session_state:
    status = st.session_state['status']
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        st.success(f"Solution found: {st.session_state['solver'].StatusName(status)}")
        st.write(f"Objective Value: {st.session_state['solver'].ObjectiveValue()}")

        # Tabs
        tab1, tab2, tab3 = st.tabs(["Classes", "Teachers", "Rooms"])

        with tab1:
            st.header("Class Timetables")
            for c in st.session_state['data']['classes']:
                df = solver._build_table_for_class(c, st.session_state['data'], st.session_state['x'], st.session_state['solver'])
                st.subheader(f"Class {c}")
                st.dataframe(df)

        with tab2:
            st.header("Teacher Timetables")
            for t in st.session_state['data']['teachers']:
                df = build_teacher_table(t, st.session_state['data'], st.session_state['x'], st.session_state['solver'])
                st.subheader(f"Teacher {t}")
                st.dataframe(df)

        with tab3:
            st.header("Room Timetables")
            for r in st.session_state['data']['rooms']:
                df = build_room_table(r, st.session_state['data'], st.session_state['x'], st.session_state['solver'])
                st.subheader(f"Room {r}")
                st.dataframe(df)

        # Download
        solution = solver.export_solution_json(st.session_state['data'], st.session_state['x'], st.session_state['solver'])
        st.download_button(
            label="Download Solution JSON",
            data=json.dumps(solution, indent=4),
            file_name="solution.json",
            mime="application/json"
        )

    else:
        st.error(f"No solution found: {st.session_state['solver'].StatusName(status)}")
        # Optionally, add more details or suggestions
"""
solver.py

Simple entrypoint that loads sample data, builds the model, solves it and prints
a readable timetable. Extend with logging, time limits and richer search strategies.
"""
from ortools.sat.python import cp_model
from .data_loader import load_data
from .model import build_model
import pandas as pd


def pretty_print_solution(data, x, solver):
    classes = data['classes']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']

    print("\n=== Timetable Solution ===\n")
    
    for c in classes:
        # Build table data for this class
        table_data = []
        for p in range(P):
            row = {'Period': f"Period {p+1}"}
            found = False
            for s in subjects:
                for t in teachers:
                    if s in data['teacher_info'][t]['can_teach']:
                        var = x[c][p][s].get(t)
                        if var is not None and solver.Value(var) == 1:
                            row['Subject'] = s
                            row['Teacher'] = t
                            found = True
                            break
                if found:
                    break
            if not found:
                row['Subject'] = 'Free'
                row['Teacher'] = '-'
            table_data.append(row)
        
        # Display table for this class
        df = pd.DataFrame(table_data)
        print(f"Class: {c}")
        print(df.to_string(index=False))
        print()


if __name__ == '__main__':
    data = load_data()
    model, x = build_model(data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 8

    res = solver.Solve(model)
    if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        pretty_print_solution(data, x, solver)
    else:
        print('No solution found')

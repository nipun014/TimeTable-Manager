"""
solver.py

Simple entrypoint that loads sample data, builds the model, solves it and prints
a readable timetable. Extend with logging, time limits and richer search strategies.
"""
from ortools.sat.python import cp_model
from .data_loader import load_data
from .model import build_model
import pandas as pd
import matplotlib.pyplot as plt


def _build_table_for_class(c, data, x, solver) -> pd.DataFrame:
    """Create a DataFrame with Period / Subject / Teacher for a class."""
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']

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
    return pd.DataFrame(table_data)


def pretty_print_solution(data, x, solver):
    classes = data['classes']

    print("\n=== Timetable Solution ===\n")

    for c in classes:
        df = _build_table_for_class(c, data, x, solver)
        print(f"Class: {c}")
        print(df.to_string(index=False))
        print()


def export_timetable_image(data, x, solver, output_path: str = "timetable.png"):
    """Render each class timetable as a grid (days x periods) with subject and teacher."""
    classes = data['classes']
    P = data['periods_per_day']
    days = data.get('days', 5)
    subjects = data['subjects']
    teachers = data['teachers']

    n = len(classes)
    fig_height = max(3 * n, 4)
    fig, axes = plt.subplots(n, 1, figsize=(12, fig_height))

    # Normalize axes to a flat list
    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]

    for ax, c in zip(axes, classes):
        # Build grid: rows = days, cols = periods
        grid_data = []
        col_headers = [f"Period {p+1}" for p in range(P)]

        for day in range(days):
            row = []
            for p in range(P):
                found = False
                for s in subjects:
                    for t in teachers:
                        if s in data['teacher_info'][t]['can_teach']:
                            var = x[c][p][s].get(t)
                            if var is not None and solver.Value(var) == 1:
                                row.append(f"{s}\n({t})")
                                found = True
                                break
                    if found:
                        break
                if not found:
                    row.append("Free")
            grid_data.append(row)

        # Create table
        ax.axis('off')
        table = ax.table(
            cellText=grid_data,
            colLabels=col_headers,
            rowLabels=[f"Day {d+1}" for d in range(days)],
            loc='center',
            cellLoc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # Style header and cells
        for i in range(len(col_headers)):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(weight='bold', color='white')

        for i in range(1, days + 1):
            table[(i, -1)].set_facecolor('#D9E1F2')
            table[(i, -1)].set_text_props(weight='bold')

        ax.set_title(f"Class: {c} - Timetable", fontsize=12, fontweight='bold', pad=12)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=200)
    plt.close(fig)
    print(f"Saved timetable image to {output_path}")


def export_teacher_timetables(data, x, solver, output_path: str = "teacher_timetables.png"):
    """Render separate timetables for each teacher (days x periods with class and subject)."""
    classes = data['classes']
    P = data['periods_per_day']
    days = data.get('days', 5)
    subjects = data['subjects']
    teachers = data['teachers']

    n = len(teachers)
    fig_height = max(3 * n, 4)
    fig, axes = plt.subplots(n, 1, figsize=(12, fig_height))

    # Normalize axes to a flat list
    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]

    for ax, t in zip(axes, teachers):
        # Build grid: rows = days, cols = periods
        grid_data = []
        col_headers = [f"Period {p+1}" for p in range(P)]

        for day in range(days):
            row = []
            for p in range(P):
                found = False
                for c in classes:
                    for s in subjects:
                        if s in data['teacher_info'][t]['can_teach']:
                            var = x[c][p][s].get(t)
                            if var is not None and solver.Value(var) == 1:
                                row.append(f"{s}\n({c})")
                                found = True
                                break
                    if found:
                        break
                if not found:
                    row.append("Free")
            grid_data.append(row)

        # Create table
        ax.axis('off')
        table = ax.table(
            cellText=grid_data,
            colLabels=col_headers,
            rowLabels=[f"Day {d+1}" for d in range(days)],
            loc='center',
            cellLoc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # Style header and cells
        for i in range(len(col_headers)):
            table[(0, i)].set_facecolor('#70AD47')
            table[(0, i)].set_text_props(weight='bold', color='white')

        for i in range(1, days + 1):
            table[(i, -1)].set_facecolor('#E2EFDA')
            table[(i, -1)].set_text_props(weight='bold')

        ax.set_title(f"Teacher: {t} - Timetable", fontsize=12, fontweight='bold', pad=12)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=200)
    plt.close(fig)
    print(f"Saved teacher timetables image to {output_path}")


if __name__ == '__main__':
    data = load_data()
    model, x = build_model(data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 8

    res = solver.Solve(model)
    if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        pretty_print_solution(data, x, solver)
        export_timetable_image(data, x, solver)
        export_teacher_timetables(data, x, solver)
    else:
        print('No solution found')

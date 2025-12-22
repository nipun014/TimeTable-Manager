"""
solver.py

Simple entrypoint that loads sample data, builds the model, solves it and prints
a readable timetable. Extend with logging, time limits and richer search strategies.
"""
from ortools.sat.python import cp_model
from .data_loader import load_data
from .model import build_model
from .validator import validate_timetable, explain_infeasibility, pre_validate_input
from .generator import export_solution_json
import pandas as pd
import matplotlib.pyplot as plt


def _build_table_for_class(c, data, x, solver) -> pd.DataFrame:
    """Create a DataFrame with Day-Period grid for a class."""
    days = data['days']
    P = data['periods_per_day']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']

    table_data = []
    for d in range(days):
        for p in range(P):
            row = {'Day': f"Day {d+1}", 'Period': f"P{p+1}"}
            found = False
            for s in subjects:
                for t in teachers:
                    if s in data['teacher_info'][t]['can_teach']:
                        if t in x[c][d][p].get(s, {}):
                            for r in rooms:
                                var = x[c][d][p][s][t].get(r)
                                if var is not None and solver.Value(var) == 1:
                                    row['Subject'] = s
                                    row['Teacher'] = t
                                    row['Room'] = r
                                    found = True
                                    break
                        if found:
                            break
                if found:
                    break
            if not found:
                row['Subject'] = 'Free'
                row['Teacher'] = '-'
                row['Room'] = '-'
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
    """Render each class timetable as a grid (days x periods) with subject, teacher, and room."""
    classes = data['classes']
    P = data['periods_per_day']
    days = data['days']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']

    n = len(classes)
    fig_height = max(3 * n, 4)
    fig, axes = plt.subplots(n, 1, figsize=(14, fig_height))

    # Normalize axes to a flat list
    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]

    for ax, c in zip(axes, classes):
        # Build grid: rows = days, cols = periods
        grid_data = []
        col_headers = [f"P{p+1}" for p in range(P)]

        for day in range(days):
            row = []
            for p in range(P):
                found = False
                for s in subjects:
                    for t in teachers:
                        if s in data['teacher_info'][t]['can_teach']:
                            if t in x[c][day][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][day][p][s][t].get(r)
                                    if var is not None and solver.Value(var) == 1:
                                        row.append(f"{s}\n{t}\n{r}")
                                        found = True
                                        break
                            if found:
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
    """Render separate timetables for each teacher (days x periods with class, subject, and room)."""
    classes = data['classes']
    P = data['periods_per_day']
    days = data['days']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']

    n = len(teachers)
    fig_height = max(3 * n, 4)
    fig, axes = plt.subplots(n, 1, figsize=(14, fig_height))

    # Normalize axes to a flat list
    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]

    for ax, t in zip(axes, teachers):
        # Build grid: rows = days, cols = periods
        grid_data = []
        col_headers = [f"P{p+1}" for p in range(P)]

        for day in range(days):
            row = []
            for p in range(P):
                found = False
                for c in classes:
                    for s in subjects:
                        if s in data['teacher_info'][t]['can_teach']:
                            if t in x[c][day][p].get(s, {}):
                                for r in rooms:
                                    var = x[c][day][p][s][t].get(r)
                                    if var is not None and solver.Value(var) == 1:
                                        row.append(f"{s}\n{c}\n{r}")
                                        found = True
                                        break
                            if found:
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


def export_room_timetables(data, x, solver, output_path: str = "room_timetables.png"):
    """Render separate timetables for each room."""
    classes = data['classes']
    P = data['periods_per_day']
    days = data['days']
    subjects = data['subjects']
    teachers = data['teachers']
    rooms = data['rooms']
    room_info = data['room_info']

    n = len(rooms)
    fig_height = max(3 * n, 4)
    fig, axes = plt.subplots(n, 1, figsize=(14, fig_height))

    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]

    for ax, r in zip(axes, rooms):
        grid_data = []
        col_headers = [f"P{p+1}" for p in range(P)]

        for day in range(days):
            row = []
            for p in range(P):
                found = False
                for c in classes:
                    for s in subjects:
                        for t in teachers:
                            if s in data['teacher_info'][t]['can_teach']:
                                if t in x[c][day][p].get(s, {}):
                                    var = x[c][day][p][s][t].get(r)
                                    if var is not None and solver.Value(var) == 1:
                                        row.append(f"{s}\n{c}\n{t}")
                                        found = True
                                        break
                            if found:
                                break
                    if found:
                        break
                if not found:
                    row.append("Empty")
            grid_data.append(row)

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

        for i in range(len(col_headers)):
            table[(0, i)].set_facecolor('#FF8C00')
            table[(0, i)].set_text_props(weight='bold', color='white')

        for i in range(1, days + 1):
            table[(i, -1)].set_facecolor('#FFE4B5')
            table[(i, -1)].set_text_props(weight='bold')

        room_type = room_info[r]['type']
        capacity = room_info[r]['capacity']
        ax.set_title(f"Room: {r} ({room_type}, Cap: {capacity})", 
                     fontsize=12, fontweight='bold', pad=12)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=200)
    plt.close(fig)
    print(f"Saved room timetables image to {output_path}")


if __name__ == '__main__':
    data = load_data()
    
    # ==== PRE-VALIDATION: Check input data before building model ====
    print("="*60)
    print("PRE-SOLVER VALIDATION")
    print("="*60)
    
    pre_validation = pre_validate_input(data)
    
    # Display informational messages
    if pre_validation.info:
        print("\n[CONFIGURATION SUMMARY]")
        for msg in pre_validation.info:
            print(f"  {msg}")
    
    # Display warnings
    if pre_validation.warnings:
        print(f"\n[WARNING] {len(pre_validation.warnings)} Warning(s):")
        for msg in pre_validation.warnings:
            print(f"  {msg}")
    
    # Display errors
    if pre_validation.errors:
        print(f"\n[ERROR] {len(pre_validation.errors)} Critical Error(s) - CANNOT PROCEED:")
        for msg in pre_validation.errors:
            print(f"  {msg}")
        print("\n" + "="*60)
        print("[ERROR] Pre-validation failed. Fix configuration and try again.")
        print("="*60)
        exit(1)
    
    # If no errors, proceed
    if not pre_validation.warnings:
        print("\n[OK] Pre-validation passed - No issues detected")
    else:
        print(f"\n[OK] Pre-validation passed with {len(pre_validation.warnings)} warning(s)")
        print("   Proceeding with caution...")
    
    print("="*60)
    print()
    
    # ==== BUILD MODEL AND SOLVE ====
    model, x = build_model(data)

    solver = cp_model.CpSolver()
    
    # Solver configuration with deterministic mode support
    solver_config = data.get('raw', {}).get('solver_config', {})
    solver.parameters.max_time_in_seconds = solver_config.get('max_time_seconds', 60)
    solver.parameters.num_search_workers = solver_config.get('num_workers', 8)
    solver.parameters.log_search_progress = solver_config.get('log_progress', True)
    
    # Set random seed if specified for reproducibility
    seed = solver_config.get('random_seed')
    if seed is not None:
        solver.parameters.random_seed = int(seed)
        print(f"[DETERMINISTIC MODE] Random seed: {seed}")

    print("Solving timetable with constraints...")
    print(f"Classes: {len(data['classes'])}")
    print(f"Days: {data['days']}, Periods/day: {data['periods_per_day']}")
    print(f"Subjects: {len(data['subjects'])}")
    print(f"Teachers: {len(data['teachers'])}")
    print(f"Rooms: {len(data['rooms'])}")
    
    res = solver.Solve(model)
    if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n[OK] Solution found! Status: {solver.StatusName(res)}")
        
        # Validate solution
        validation = validate_timetable(data, x, solver)
        if validation.is_valid:
            print(f"[OK] All constraints satisfied")
        else:
            print(f"[WARNING] {len(validation.violations)} constraint violations found:")
            for v in validation.violations[:10]:  # Show first 10
                print(f"  - {v}")
            if len(validation.violations) > 10:
                print(f"  ... and {len(validation.violations) - 10} more")
        
        # Show optimization score
        try:
            print(f"📊 Optimization Score (Total Penalty): {solver.ObjectiveValue():.2f}")
        except:
            pass
        
        pretty_print_solution(data, x, solver)
        export_timetable_image(data, x, solver)
        export_teacher_timetables(data, x, solver)
        export_room_timetables(data, x, solver)
        export_solution_json(data, x, solver)
    else:
        print(f'\n[ERROR] No solution found. Status: {solver.StatusName(res)}')
        suggestions = explain_infeasibility(data)
        if suggestions:
            print("\n🔍 Possible reasons:")
            for s in suggestions:
                print(f"  {s}")

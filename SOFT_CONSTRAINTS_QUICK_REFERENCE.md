# Soft Constraints Quick Reference

## Configuration in `sample_data.json`

### 1. Penalty Weights
```json
"weights": {
  "teacher_unavailable": 10,           // High penalty for unavailable teachers
  "teacher_idle_transition": 2,        // Moderate penalty for fragmented schedules
  "class_consecutive_overrun": 3,      // Moderate penalty for too many consecutive periods
  "subject_spread_excess": 2,          // Moderate penalty for clustering subjects
  "heavy_back_to_back": 1,             // Light penalty for consecutive heavy subjects
  "teacher_early_late_imbalance": 1    // Light penalty for unbalanced teacher loads
}
```

### 2. Thresholds and Periods
```json
"max_consecutive_periods": 3,    // Maximum consecutive periods before penalty
"early_periods": [0, 1],         // Periods considered "early" (P1, P2)
"late_periods": [4, 5]           // Periods considered "late" (P5, P6)
```

### 3. Subject Properties
```json
"Math": {
  "hours_per_week": 3,
  "room_type": "standard",
  "is_heavy": true              // Marks subject as heavy (avoid back-to-back)
}
```

### 4. Teacher Availability (Soft)
```json
"Dr_Sharma": {
  "can_teach": ["Math", "Physics"],
  "availability": [             // 0 = unavailable (penalty), 1 = available
    [1, 1, 0, 1, 1, 1],        // Day 1: P3 unavailable
    [1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1]
  ]
}
```

## How to Customize

### Disable a Soft Constraint
Set its weight to 0:
```json
"weights": {
  "heavy_back_to_back": 0      // Disabled
}
```

### Prioritize a Soft Constraint
Increase its weight (higher = more important):
```json
"weights": {
  "subject_spread_excess": 10   // Very high priority
}
```

### Adjust Consecutive Period Limit
Change the threshold:
```json
"max_consecutive_periods": 4    // Allow up to 4 consecutive periods
```

### Change Early/Late Period Definitions
Modify the period ranges (0-indexed):
```json
"early_periods": [0, 1, 2],     // P1, P2, P3 are early
"late_periods": [3, 4, 5]       // P4, P5, P6 are late
```

## Expected Objective Values

### Typical Range (with default weights)
- **Excellent:** 0-20 (minimal violations)
- **Good:** 20-40 (some clustering, few transitions)
- **Acceptable:** 40-80 (moderate violations)
- **Poor:** 80+ (significant violations, consider tuning)

### Last Run Results
- **Objective:** 24 (Good quality)
- **Best Bound:** 6 (optimal lower bound)
- **Status:** FEASIBLE
- **Time:** 30.13 seconds

## Interpreting Penalties

### teacher_unavailable (Weight: 10)
- **Per violation:** +10 penalty
- **Example:** Scheduling a teacher during unavailable period = +10

### teacher_idle_transition (Weight: 2)
- **Per transition:** +2 penalty
- **Example:** Teacher has classes P1, P3 (gap at P2) = 2 transitions = +4

### class_consecutive_overrun (Weight: 3)
- **Per excess period:** +3 penalty
- **Example:** Class has 5 consecutive periods (2 beyond threshold of 3) = +6

### subject_spread_excess (Weight: 2)
- **Per excess period per day:** +2 penalty
- **Example:** Math has 3 periods on Day 1 (2 excess beyond 1) = +4

### heavy_back_to_back (Weight: 1)
- **Per occurrence:** +1 penalty
- **Example:** Math → Physics (both heavy, consecutive) = +1

### teacher_early_late_imbalance (Weight: 1)
- **Per imbalance unit:** +1 penalty
- **Example:** Teacher has 3 early, 0 late periods (imbalance = 3) = +3

## Common Tuning Scenarios

### Scenario 1: Too Much Subject Clustering
**Problem:** Multiple periods of same subject on one day

**Solution:** Increase `subject_spread_excess` weight
```json
"subject_spread_excess": 5
```

### Scenario 2: Teachers Want Grouped Schedules
**Problem:** Teachers prefer fewer transitions (compact schedules)

**Solution:** Keep `teacher_idle_transition` low or zero
```json
"teacher_idle_transition": 0
```

### Scenario 3: Strict Availability Enforcement
**Problem:** Unavailable teachers being scheduled

**Solution:** Increase `teacher_unavailable` weight dramatically
```json
"teacher_unavailable": 100
```

### Scenario 4: Students Need More Breaks
**Problem:** Too many consecutive periods without breaks

**Solution:** Lower threshold and increase penalty
```json
"max_consecutive_periods": 2,
"class_consecutive_overrun": 10
```

## Verification Commands

### Run Solver
```bash
python -m timetable_solver.solver
```

### Check Objective Value
Look for this line in output:
```
objective: 24
```

### Verify All Constraints
Hard constraints are always satisfied (or solver returns INFEASIBLE).
Soft constraints show in objective value.

## Files to Modify

1. **`sample_data.json`** - Configuration (weights, thresholds, availability)
2. **`model.py`** - Constraint logic (only if changing constraint definitions)
3. **`solver.py`** - Visualization (only if changing output format)

## Support

For detailed documentation, see:
- `TIMETABLE_SYSTEM_DOCUMENTATION.md` - Full system reference
- `SOFT_CONSTRAINTS_REPORT.md` - Implementation details and analysis

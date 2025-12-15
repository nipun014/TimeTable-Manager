"""
data_loader.py

Load the sample JSON data and provide simple accessor structures.
"""
from pathlib import Path
import json
from typing import Dict, List

DATA_FILE = Path(__file__).parent / 'sample_data.json'


def load_data(path: Path = DATA_FILE) -> Dict:
    with open(path, 'r') as f:
        data = json.load(f)
    # Basic normalization and convenience structures
    classes = data['classes']
    periods_per_day = data.get('periods_per_day', 4)
    subjects = list(data['subjects'].keys())
    teachers = list(data['teachers'].keys())

    # teacher availability: map teacher -> list of lists (days x periods)
    # For this scaffold we treat availability as days==number of classes (simple)
    teacher_info = data['teachers']

    return {
        'classes': classes,
        'periods_per_day': periods_per_day,
        'subjects': subjects,
        'teachers': teachers,
        'teacher_info': teacher_info,
        'raw': data
    }

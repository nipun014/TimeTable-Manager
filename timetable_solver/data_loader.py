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
    days = data.get('days', 5)
    periods_per_day = data.get('periods_per_day', 6)
    subjects = list(data['subjects'].keys())
    teachers = list(data['teachers'].keys())
    rooms = list(data.get('rooms', {}).keys())

    # teacher availability: map teacher -> list of lists (days x periods)
    teacher_info = data['teachers']
    
    # room information
    room_info = data.get('rooms', {})
    
    # subject details with constraint information
    subject_info = data['subjects']

    return {
        'classes': classes,
        'days': days,
        'periods_per_day': periods_per_day,
        'subjects': subjects,
        'teachers': teachers,
        'rooms': rooms,
        'teacher_info': teacher_info,
        'room_info': room_info,
        'subject_info': subject_info,
        'raw': data
    }

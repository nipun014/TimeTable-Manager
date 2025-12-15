"""
constraints.py

Define hard/soft constraints as functions or classes. For the scaffold we include
simple constraint checkers that are applied after extraction.
"""

from typing import Dict


class Constraints:
    """Placeholder constraints container. Extend per project needs."""

    def __init__(self, data: Dict):
        self.data = data

    # example: ensure a teacher is qualified for a subject
    def teacher_can_teach(self, teacher: str, subject: str) -> bool:
        return subject in self.data['teacher_info'][teacher]['can_teach']


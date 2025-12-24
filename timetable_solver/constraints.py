from typing import Dict


class Constraints:
    def __init__(self, data: Dict):
        self.data = data

    def teacher_can_teach(self, teacher: str, subject: str) -> bool:
        return subject in self.data['teacher_info'][teacher]['can_teach']


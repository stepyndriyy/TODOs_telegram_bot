from datetime import timedelta
from models import RecurrencePattern


def calculate_next_deadline(todo):
    if todo.recurrence_pattern == RecurrencePattern.DAILY:
        return todo.deadline + timedelta(days=1)
    elif todo.recurrence_pattern == RecurrencePattern.WEEKLY:
        return todo.deadline + timedelta(weeks=1)
    elif todo.recurrence_pattern == RecurrencePattern.MONTHLY:
        return todo.deadline + timedelta(days=30)

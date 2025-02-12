from models import Importance, RecurrencePattern
from telegram import InlineKeyboardButton, ReplyKeyboardMarkup


def details_keyboard_buttons(todo_id):
    return [
        [
            InlineKeyboardButton("✅ Done", callback_data=f"done_{todo_id}"),
            InlineKeyboardButton("❌ Close", callback_data=f"closed_{todo_id}"),
            InlineKeyboardButton("⚠️ Failed", callback_data=f"failed_{todo_id}")
        ],
        [
            InlineKeyboardButton("⏰ Postpone", callback_data=f"delay_{todo_id}")
        ]
    ]

def postpone_keyboard_buttons(todo_id):
    return [
        [
            InlineKeyboardButton("Tomorrow", callback_data=f"postpone_{todo_id}_tomorrow"),
            InlineKeyboardButton("Custom date", callback_data=f"custompostpone_{todo_id}")
        ]
    ]


def importance_keyboard():
    return [[level.name for level in Importance]]


def date_selection_keyboard():
    return [
        ["Today", "Tomorrow"],
        ["In 2 days", "In 3 days"],
    ]

def time_selection_keyboard():
    return [
        ["09:00", "12:00", "15:00"],
        ["18:00", "20:00", "22:00"],
    ]

def reminder_keyboard():
    return [["15", "30", "60"]]

def recurrence_keyboard():
    return [
        ["NO"],
        [pattern.name for pattern in RecurrencePattern]
    ]

def reminder_action_buttons(todo_id):
    return [
        [
            InlineKeyboardButton("✅ Done", callback_data=f"done_{todo_id}"),
            InlineKeyboardButton("📋 Details", callback_data=f"details_{todo_id}")
        ]
    ]
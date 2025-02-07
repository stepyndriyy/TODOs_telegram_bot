# Command messages
START_MESSAGE = """
🤖 Welcome to TODO bot!
It is a simple bot to manage your TODOs. You can create recursive tasks amd set reminders.
Also it will remind you about your tasks every day.

Available commands:
📝 /add - Add new TODO
📋 /list - Show and state TODOs
🔍 /history - View completed tasks with filter

✅ /done|/close|/fail - Mark TODO state
"""

ADD_HELP_MESSAGE = """

📝 Please use format:
/add Task text | importance | YYYY-MM-DD HH:MM | minutes_before | recurrence

Example:
/add Buy groceries | HIGH | 2024-01-20 18:00 | 30 | DAILY

Importance levels:
🟢 LOW
🟡 MEDIUM
🔴 HIGH

Recurrence options:
🔁 DAILY
🔁 WEEKLY
🔁 MONTHLY
"""

# List view messages
NO_TODOS_MESSAGE = "📭 No active TODOs!"

TODO_LIST_HEADER = "📋 Your TODOs:\n\n"

TODO_ITEM_TEMPLATE = """
🔸 ID: {id}
📝 Task: {text}
⚡️ Importance: {importance}
⏰ Deadline: {deadline}
⏳ Reminder: {reminder} minutes before
──────────────────
"""

# Status messages
TODO_ADDED_SUCCESS = "✅ TODO added successfully! 🔔 reminded {minutes} minutes before. Recurrence: {reccurence}"
TODO_DONE_SUCCESS = "✅ TODO marked as done!"
TODO_NOT_FOUND = "❌ TODO not found!"
DONE_HELP_MESSAGE = "ℹ️ Please use format: /done <todo_id>"

# Reminder message
REMINDER_MESSAGE = "⚠️ Reminder: '{text}' is due in {minutes} minutes!"


#add messages
TODO_CREEATION_TITLE = "Enter task title:"
TODO_CRETATION_IMPORTANCE = "Select importance:"
TODO_CRETATION_DEADLINE = "Enter deadline (YYYY-MM-DD HH:MM)"
TODO_CRETATION_DEADLINE_ERROR = "Invalid date format. Please use YYYY-MM-DD HH:MM"
TODO_CRETATION_REMINDER = "How many minutes before to remind?"
TODO_CRETATION_RECURRENCE = "Select recurrence pattern:"

import logging
from datetime import datetime, timedelta, time
from functools import partial
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from models import Session, Todo, Importance, TodoStatus, RecurrencePattern
from config import BOT_TOKEN
from messages import START_MESSAGE, ADD_HELP_MESSAGE, NO_TODOS_MESSAGE, TODO_LIST_HEADER, TODO_ITEM_TEMPLATE, TODO_ADDED_SUCCESS, TODO_DONE_SUCCESS, TODO_NOT_FOUND, DONE_HELP_MESSAGE, REMINDER_MESSAGE
from utils import calculate_next_deadline
from create_todo import create_todo_conversation_handler

logging.basicConfig(level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE)


async def add_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # New format: /add Important task | HIGH | 2024-01-01 12:00 | 30
    try:
        text = update.message.text.replace('/add ', '')
        parts = text.split('|')
        todo_text = parts[0].strip()
        importance = Importance[parts[1].strip()]
        deadline = datetime.strptime(parts[2].strip(), '%Y-%m-%d %H:%M')
        reminder_minutes = int(parts[3].strip()) if len(parts) > 3 else 60
        recurrence = RecurrencePattern[parts[4].strip()] if len(parts) > 4 else None

        session = Session()
        todo = Todo(
            user_id=update.effective_user.id,
            text=todo_text,
            importance=importance,
            deadline=deadline,
            reminder_minutes=reminder_minutes,
            is_recurring=bool(recurrence),
            recurrence_pattern=recurrence,
            parent_id=None,
        )
        session.add(todo)
        session.commit()
        session.close()
        await update.message.reply_text(TODO_ADDED_SUCCESS.format(minutes=reminder_minutes, recurrence=recurrence.value if recurrence else "No"))
    except Exception as e:
        await update.message.reply_text(ADD_HELP_MESSAGE)


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    now = datetime.now()
    todos = session.query(Todo).filter(
        Todo.deadline > now,
        Todo.status == TodoStatus.ACTIVE,
        Todo.reminder_sent == False
    ).all()

    for todo in todos:
        time_diff = todo.deadline - now
        minutes_until_deadline = time_diff.total_seconds() / 60
        if minutes_until_deadline <= todo.reminder_minutes:
            await context.bot.send_message(
                chat_id=todo.user_id,
                text=REMINDER_MESSAGE.format(text=todo.text, minutes=int(minutes_until_deadline))
            )
            todo.reminder_sent = True

    session.commit()
    session.close()


async def list_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    todos = session.query(Todo).filter_by(
        user_id=update.effective_user.id,
        status=TodoStatus.ACTIVE
    ).all()
    
    if not todos:
        await update.message.reply_text(NO_TODOS_MESSAGE)
        return

    for todo in todos:
        text = TODO_ITEM_TEMPLATE.format(
            id=todo.id,
            text=todo.text,
            importance=todo.importance.name,
            deadline=todo.deadline.strftime('%Y-%m-%d %H:%M'),
            reminder=todo.reminder_minutes
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Done", callback_data=f"done_{todo.id}"),
                InlineKeyboardButton("❌ Close", callback_data=f"closed_{todo.id}"),
                InlineKeyboardButton("⚠️ Failed", callback_data=f"failed_{todo.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    session.close()


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, todo_id = query.data.split('_')
    
    session = Session()
    todo = session.query(Todo).filter_by(
        id=int(todo_id),
        user_id=update.effective_user.id
    ).first()
    print(action)
    print(todo.status)
    print(todo_id)
    if todo:
        todo.status = TodoStatus[action.upper()]
        print(todo.status)

        # Create next instance if it's a recurring todo
        if todo.is_recurring and action == 'done':
            next_deadline = calculate_next_deadline(todo)
            new_todo = Todo(
                user_id=todo.user_id,
                text=todo.text,
                importance=todo.importance,
                deadline=next_deadline,
                reminder_minutes=todo.reminder_minutes,
                is_recurring=True,
                recurrence_pattern=todo.recurrence_pattern,
                parent_id=todo.id
            )
            session.add(new_todo)

        session.commit()
        await query.answer(f"Todo marked as {action}")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(f"Todo: '{todo.text}' marked as {action}")
    
    session.close()


async def change_todo_state(update: Update, context: ContextTypes.DEFAULT_TYPE, new_state: TodoStatus):
    try:
        command_name = update.message.text.split()[0][1:]  # Remove the '/' from command
        todo_id = int(update.message.text.replace(f'/{command_name} ', ''))
        
        session = Session()
        todo = session.query(Todo).filter_by(
            id=todo_id,
            user_id=update.effective_user.id
        ).first()
        
        if todo:
            todo.status = new_state
            session.commit()
            await update.message.reply_text(f"TODO marked as {new_state.value}!")
        else:
            await update.message.reply_text("TODO not found!")
        
        session.close()
    except:
        await update.message.reply_text(f"Please use format: /{command_name} <todo_id>")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Last Week", callback_data="history_week"),
            InlineKeyboardButton("Last Month", callback_data="history_month")
        ],
        [
            InlineKeyboardButton("Done", callback_data="history_done"),
            InlineKeyboardButton("Failed", callback_data="history_failed"),
            InlineKeyboardButton("Closed", callback_data="history_closed")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select filter for completed tasks:", reply_markup=reply_markup)


async def handle_history_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    query = update.callback_query
    filter_type = query.data.split('_')[1]
    print(query)
    session = Session()
    base_query = session.query(Todo).filter_by(user_id=update.effective_user.id)
    
    if filter_type == 'week':
        week_ago = datetime.now() - timedelta(days=7)
        todos = base_query.filter(Todo.status != TodoStatus.ACTIVE, Todo.deadline >= week_ago).all()
    elif filter_type == 'month':
        month_ago = datetime.now() - timedelta(days=30)
        todos = base_query.filter(Todo.status != TodoStatus.ACTIVE, Todo.deadline >= month_ago).all()
    else:
        status = TodoStatus[filter_type.upper()]
        todos = base_query.filter_by(status=status).all()
    
    if not todos:
        await query.edit_message_text("No tasks found with selected filter!")
        return
    
    response = "📋 Task History:\n\n"
    for todo in todos:
        response += TODO_ITEM_TEMPLATE.format(
            id=todo.id,
            text=todo.text,
            importance=todo.importance.name,
            deadline=todo.deadline.strftime('%Y-%m-%d %H:%M'),
            reminder=todo.reminder_minutes
        )
        response += f"Status: {todo.status.value}\n"
        response += "──────────────────\n"
    
    await query.edit_message_text(response)
    session.close()


async def send_daily_todos(context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    today = datetime.now().date()
    
    # Get all active todos for today grouped by user
    todos_by_user = {}
    todos = session.query(Todo).filter(
        Todo.status == TodoStatus.ACTIVE,
        func.date(Todo.deadline) == today
    ).all()
    
    for todo in todos:
        if todo.user_id not in todos_by_user:
            todos_by_user[todo.user_id] = []
        todos_by_user[todo.user_id].append(todo)
    
    # Send daily briefing to each user who has todos
    for user_id, user_todos in todos_by_user.items():
        if not user_todos:
            continue
            
        message = "🌅 Your tasks for today:\n\n"
        for todo in user_todos:
            message += TODO_ITEM_TEMPLATE.format(
                id=todo.id,
                text=todo.text,
                importance=todo.importance.name,
                deadline=todo.deadline.strftime('%H:%M'),
                reminder=todo.reminder_minutes
            )
        
        await context.bot.send_message(chat_id=user_id, text=message)
    
    session.close()


async def setup_commands(application):
    commands = [
        ("start", "Start the bot and see available commands"),
        ("add", "Add new todo (format: text | importance | YYYY-MM-DD HH:MM | minutes_before)"),
        ("list", "Show all active todos"),
        ("history", "View completed tasks with filters")
        # ("done|close|fail", "Mark todo state (format: /done <todo_id>)"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    # app.add_handler(CommandHandler("add", add_todo))
    app.add_handler(CommandHandler("list", list_todos))
    app.add_handler(CommandHandler("done", partial(change_todo_state, new_state=TodoStatus.DONE)))
    app.add_handler(CommandHandler("close", partial(change_todo_state, new_state=TodoStatus.CLOSED)))
    app.add_handler(CommandHandler("fail", partial(change_todo_state, new_state=TodoStatus.FAILED)))
    app.add_handler(CommandHandler("history", history))
    
    # Callback handlers with patterns
    app.add_handler(CallbackQueryHandler(handle_history_filter, pattern="^history_"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(done|closed|failed)_"))
    
    # Conversation handler
    app.add_handler(create_todo_conversation_handler())

    # Add reminder job
    job_queue = app.job_queue
    job_queue.run_repeating(check_reminders, interval=60)  # Check every minute

    # Add daily job at 10:00 AM
    job_queue = app.job_queue
    job_queue.run_daily(send_daily_todos, time=time(10, 0))
    
    # Setup commands menu
    app.job_queue.run_once(setup_commands, when=1, data=app)
    
    app.run_polling()


if __name__ == '__main__':
    main()

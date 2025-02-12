import logging
import math
from datetime import datetime, timedelta, time
from functools import partial
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from models import Session, Todo, Importance, TodoStatus, RecurrencePattern
from config import BOT_TOKEN
from messages import START_MESSAGE, ADD_HELP_MESSAGE, NO_TODOS_MESSAGE, TODO_LIST_HEADER, TODO_ITEM_TEMPLATE, TODO_ADDED_SUCCESS, TODO_DONE_SUCCESS, TODO_NOT_FOUND, DONE_HELP_MESSAGE, REMINDER_MESSAGE, REMINDER_OVERDUE_MESSAGE
from utils import calculate_next_deadline
from create_todo import create_todo_conversation_handler
from list_handler import TodoListHandler
from button_handler import ButtonHandler
from keyboard import details_keyboard_buttons, reminder_action_buttons
from natural_language_parser import TodoParser


logging.basicConfig(level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE)


async def display_todos(update: Update, todos: list, header: str = None):
    if not todos:
        await update.message.reply_text(NO_TODOS_MESSAGE)
        return
        
    if header:
        await update.message.reply_text(header)
    
    for todo in todos:
        text = TODO_ITEM_TEMPLATE.format(
            id=todo.id,
            text=todo.text,
            importance=todo.importance.name,
            deadline=todo.deadline.strftime('%Y-%m-%d %H:%M'),
            reminder=todo.reminder_minutes
        )
        keyboard = details_keyboard_buttons(todo.id)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    now = datetime.now()
    todos = session.query(Todo).filter(
        Todo.deadline > now,
        Todo.status == TodoStatus.ACTIVE,
        Todo.reminder_sent == False
    ).all()

    for todo in todos:
        keyboard = reminder_action_buttons(todo.id)
        time_diff = todo.deadline - now
        minutes_until_deadline = time_diff.total_seconds() / 60
        if minutes_until_deadline <= todo.reminder_minutes:
            await context.bot.send_message(
                chat_id=todo.user_id,
                text=REMINDER_MESSAGE.format(text=todo.text, minutes=math.ceil(minutes_until_deadline)),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            todo.reminder_sent = True

    # Post-deadline notifications
    overdue_todos = session.query(Todo).filter(
        Todo.deadline <= now,
        Todo.status == TodoStatus.ACTIVE
    ).all()

    for todo in overdue_todos:
        keyboard = reminder_action_buttons(todo.id)
        time_diff = now - todo.deadline
        minutes_past_deadline = time_diff.total_seconds() / 60
        
        # Notify at deadline and every 30 minutes after
        if (0 <= minutes_past_deadline < 1) or (abs(minutes_past_deadline % 30) < 1):
            await context.bot.send_message(
                chat_id=todo.user_id,
                text=REMINDER_OVERDUE_MESSAGE.format(text=todo.text, minutes=math.ceil(minutes_past_deadline)),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    session.commit()
    session.close()


async def list_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    todos = session.query(Todo).filter_by(
        user_id=update.effective_user.id,
        status=TodoStatus.ACTIVE
    ).order_by(Todo.importance.desc(), Todo.deadline.asc()).all()
    
    await display_todos(update, todos)
    session.close()


async def show_smart_list(update: Update, context: ContextTypes.DEFAULT_TYPE, days: int = 0):
    session = Session()
    now = datetime.now()
    
    if days == 0:
        start_date = now.date()
        end_date = start_date + timedelta(days=1)
        title = "📝 Today's tasks"
    elif days == 7:
        start_date = now.date()
        end_date = start_date + timedelta(days=7)
        title = "📅 This week's tasks"
    
    todos = session.query(Todo).filter(
        Todo.user_id == update.effective_user.id,
        Todo.status == TodoStatus.ACTIVE,
        Todo.deadline <= end_date
    ).order_by(Todo.importance.desc(), Todo.deadline.asc()).all()
    
    await display_todos(update, todos, title)
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


async def quick_add_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parser = TodoParser()
    todo_data = parser.parse_todo(update.message.text)
    
    session = Session()
    todo = Todo(
        user_id=update.effective_user.id,
        text=todo_data['text'],
        importance=todo_data['importance'],
        deadline=todo_data['deadline'],
        reminder_minutes=todo_data['reminder_minutes'],
        is_recurring=todo_data['is_recurring'],
        recurrence_pattern=todo_data['recurrence_pattern']
    )
    session.add(todo)
    session.commit()
    session.close()
    
    await update.message.reply_text(
        f"✅ Added task: {todo_data['text']}\n"
        f"Priority: {todo_data['importance'].name}\n"
        f"Deadline: {todo_data['deadline'].strftime('%Y-%m-%d %H:%M')}"
    )


async def setup_commands(application):
    commands = [
        ("start", "Start the bot and see available commands"),
        ("add", "Add new todo (format: text | importance | YYYY-MM-DD HH:MM | minutes_before)"),
        ("list", "Show all active todos"),
        ("history", "View completed tasks with filters"),
        ("today", "Show today's tasks"),
        ("week", "Show this week's tasks"),
        # ("done|close|fail", "Mark todo state (format: /done <todo_id>)"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Initialize list handler
    list_handler = TodoListHandler()
    button_handler = ButtonHandler()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", partial(change_todo_state, new_state=TodoStatus.DONE)))
    app.add_handler(CommandHandler("close", partial(change_todo_state, new_state=TodoStatus.CLOSED)))
    app.add_handler(CommandHandler("fail", partial(change_todo_state, new_state=TodoStatus.FAILED)))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("list", list_handler.list_tasks))
    app.add_handler(CommandHandler("today", partial(list_handler.list_tasks, days=0)))
    app.add_handler(CommandHandler("week", partial(list_handler.list_tasks, days=7)))

    
    # Callback handlers with patterns
    app.add_handler(CallbackQueryHandler(handle_history_filter, pattern="^history_"))
    # app.add_handler(CallbackQueryHandler(button_handler, pattern="^(done|closed|failed|delay|postpone)_"))
    app.add_handler(CallbackQueryHandler(button_handler.handle, pattern="^(done|closed|failed|delay|postpone)_"))
    app.add_handler(CallbackQueryHandler(list_handler.show_details, pattern="^details_"))

    # Conversation handler
    app.add_handler(create_todo_conversation_handler())
    app.add_handler(button_handler.get_custom_date_handler())

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quick_add_todo))

    # Add reminder job
    job_queue = app.job_queue
    job_queue.run_repeating(check_reminders, interval=60)  # Check every minute

    # Add daily job at 10:00 AM
    job_queue = app.job_queue
    job_queue.run_daily(send_daily_todos, time=time(7, 0))
    
    # Setup commands menu
    app.job_queue.run_once(setup_commands, when=1, data=app)
    
    app.run_polling()


if __name__ == '__main__':
    main()

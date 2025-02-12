import logging
from datetime import datetime, timedelta
from functools import partial
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from models import Session, Todo, Importance, RecurrencePattern
from messages import TODO_CREEATION_TITLE, TODO_CRETATION_IMPORTANCE, TODO_CRETATION_DEADLINE, TODO_CRETATION_DEADLINE_ERROR, TODO_CRETATION_REMINDER, TODO_CRETATION_RECURRENCE, TODO_ADDED_SUCCESS
from utils import calculate_next_deadline
from keyboard import date_selection_keyboard, time_selection_keyboard, reminder_keyboard, recurrence_keyboard


TITLE, IMPORTANCE, DATE, TIME, REMINDER, RECURRENCE = range(6)


async def start_add_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TODO_CREEATION_TITLE)
    return TITLE


async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    keyboard = [[level.name for level in Importance]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(TODO_CRETATION_IMPORTANCE, reply_markup=reply_markup)
    return IMPORTANCE


async def get_importance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['importance'] = update.message.text
    keyboard = date_selection_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(TODO_CRETATION_DEADLINE, reply_markup=reply_markup)
    return DATE


async def get_deadline_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    today = datetime.now()
    
    if text == "Today":
        date = today
    elif text == "Tomorrow":
        date = today + timedelta(days=1)
    elif text == "In 2 days":
        date = today + timedelta(days=2)
    elif text == "In 3 days":
        date = today + timedelta(days=3)
    else:
        # Try to parse custom date
        date = datetime.strptime(text, '%Y-%m-%d')
        if date.date() < today.date():
            await update.message.reply_text(TODO_CRETATION_DEADLINE_ERROR)
            return DATE
    
    context.user_data['date'] = date
    keyboard = time_selection_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Select time:", reply_markup=reply_markup)
    return TIME


async def process_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    try:
        if ':' in text:  # Custom time input
            hour, minute = map(int, text.split(':'))
        else:  # Quick option
            hour, minute = map(int, text.split(':'))
        
        date = context.user_data['date']
        deadline = date.replace(hour=hour, minute=minute)
        context.user_data['deadline'] = deadline
        
        keyboard = reminder_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(TODO_CRETATION_REMINDER, reply_markup=reply_markup)
        return REMINDER
    except ValueError:
        await update.message.reply_text("Invalid time format. Please use HH:MM")
        return TIME


async def get_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reminder'] = int(update.message.text)
    keyboard = recurrence_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(TODO_CRETATION_RECURRENCE, reply_markup=reply_markup)
    return RECURRENCE


async def save_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recurrence = None if update.message.text == "NO" else RecurrencePattern[update.message.text]
    
    session = Session()
    todo = Todo(
        user_id=update.effective_user.id,
        text=context.user_data['title'],
        importance=Importance[context.user_data['importance']],
        deadline=context.user_data['deadline'],
        reminder_minutes=context.user_data['reminder'],
        is_recurring=bool(recurrence),
        recurrence_pattern=recurrence,
        parent_id=None
    )
    session.add(todo)
    session.commit()
    session.close()
    
    await update.message.reply_text(
        TODO_ADDED_SUCCESS.format(
            minutes=context.user_data['reminder'],
            reccurence=recurrence.value if recurrence else "No"
        ),
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def create_todo_conversation_handler():
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', start_add_todo)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            IMPORTANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_importance)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_deadline_time)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_time)],
            REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_reminder)],
            RECURRENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_todo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    return conv_handler

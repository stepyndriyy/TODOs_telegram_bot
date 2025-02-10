from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models import Session, Todo, TodoStatus
from sqlalchemy import func

class TodoListHandler:
    def __init__(self):
        self.compact_template = "📌 {importance} {text}\n⏰ {deadline}\n"
    
    async def _display_todos(self, update: Update, todos: list, header: str = None):
        if not todos:
            await update.message.reply_text("No tasks found!")
            return
            
        if header:
            await update.message.reply_text(header)
        
        for todo in todos:
            text = self.compact_template.format(
                importance="❗" * todo.importance.value,
                text=todo.text,
                deadline=todo.deadline.strftime('%Y-%m-%d %H:%M')
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Done", callback_data=f"done_{todo.id}"),
                    InlineKeyboardButton("ℹ️ Details", callback_data=f"details_{todo.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)


    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE, days: int = None):
        session = Session()
        now = datetime.now()
        
        query = session.query(Todo).filter(
            Todo.user_id == update.effective_user.id,
            Todo.status == TodoStatus.ACTIVE
        )

        if days is not None:
            end_date = now.date() + timedelta(days=days)
            query = query.filter(func.date(Todo.deadline) <= end_date)

        todos = query.order_by(Todo.deadline.asc(), Todo.importance.desc()).all()
        
        headers = {
            0: "📝 Today's tasks:",
            7: "📅 This week's tasks:",
            None: "📋 All active tasks:"
        }
        
        await self._display_todos(update, todos, headers[days])
        session.close()

    async def show_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        todo_id = int(query.data.split('_')[1])
        
        session = Session()
        todo = session.query(Todo).filter_by(
            id=todo_id,
            user_id=update.effective_user.id
        ).first()
        
        if todo:
            detailed_text = (
                f"📌 Task: {todo.text}\n"
                f"❗ Importance: {todo.importance.name}\n"
                f"⏰ Deadline: {todo.deadline.strftime('%Y-%m-%d %H:%M')}\n"
                f"⚡ Reminder: {todo.reminder_minutes} minutes before"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Done", callback_data=f"done_{todo.id}"),
                    InlineKeyboardButton("❌ Close", callback_data=f"close_{todo.id}"),
                    InlineKeyboardButton("⚠️ Failed", callback_data=f"fail_{todo.id}")
                ],
                [
                    InlineKeyboardButton("⏰ Postpone", callback_data=f"delay_{todo.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(detailed_text, reply_markup=reply_markup)
        
        session.close()
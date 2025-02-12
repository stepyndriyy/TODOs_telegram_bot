from datetime import timedelta, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from models import Session, Todo, TodoStatus
from utils import calculate_next_deadline
from keyboard import postpone_keyboard_buttons

class ButtonHandler:
    WAITING_FOR_NEW_DATE = 1

    def __init__(self):
        self.actions = {
            'delay': self._handle_delay,
            'postpone': self._handle_postpone,
            'done': self._handle_status_change,
            'closed': self._handle_status_change,
            'failed': self._handle_status_change
        }

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        action, todo_id = query.data.split('_')[:2]
        print(action, todo_id)
        if action in self.actions:
            await self.actions[action](update, context, todo_id)

    async def _handle_delay(self, update: Update, context: ContextTypes.DEFAULT_TYPE, todo_id: str):
        keyboard = postpone_keyboard_buttons(todo_id)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    async def _handle_postpone(self, update: Update, context: ContextTypes.DEFAULT_TYPE, todo_id: str):
        query = update.callback_query
        delay_type = query.data.split('_')[2]
        
        session = Session()
        todo = self._get_todo(session, todo_id, update.effective_user.id)
        
        if not todo:
            await query.answer("Todo not found!")
            return

        if delay_type == 'tomorrow':
            tomorrow = todo.deadline + timedelta(days=1)
            todo.deadline = tomorrow
            todo.reminder_sent = False
            session.commit()
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(f"Todo: '{todo.text}' postponed to tomorrow")
        else:
            # unable to reach this point
            print('unable to reach this point postpone')
            pass
        
        session.close()

    async def _handle_status_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE, todo_id: str):
        query = update.callback_query
        action = query.data.split('_')[0]
        
        session = Session()
        todo = self._get_todo(session, todo_id, update.effective_user.id)
        
        if not todo:
            await query.answer("Todo not found!")
            return

        todo.status = TodoStatus[action.upper()]
        print(f"Todo status changed to {TodoStatus[action.upper()]}")
        if todo.is_recurring and action == 'done':
            self._create_next_recurring_todo(session, todo)
            
        session.commit()
        await query.answer(f"Todo marked as {action}")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(f"Todo: '{todo.text}' marked as {action}")
        
        session.close()

    def _get_todo(self, session: Session, todo_id: str, user_id: int) -> Todo:
        return session.query(Todo).filter_by(
            id=int(todo_id),
            user_id=user_id
        ).first()

    def _create_next_recurring_todo(self, session: Session, todo: Todo):
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

    def get_custom_date_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self._start_custom_date, pattern="^custompostpone_\d+$")
            ],
            states={
                self.WAITING_FOR_NEW_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._process_custom_date)
                ]
            },
            fallbacks=[]
        )

    async def _start_custom_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        todo_id = query.data.split('_')[1]
        context.user_data['postpone_todo_id'] = todo_id
        await query.edit_message_text("Enter new date and time (YYYY-MM-DD HH:MM):")
        return self.WAITING_FOR_NEW_DATE

    async def _process_custom_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            new_date = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
            todo_id = context.user_data['postpone_todo_id']
            
            session = Session()
            todo = self._get_todo(session, todo_id, update.effective_user.id)
            
            if todo:
                todo.deadline = new_date
                todo.reminder_sent = False
                session.commit()
                await update.message.reply_text(f"Todo: '{todo.text}' postponed to {new_date}")
            
            session.close()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD HH:MM")
            return self.WAITING_FOR_NEW_DATE
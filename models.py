from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

Base = declarative_base()

class Importance(enum.Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class TodoStatus(enum.Enum):
    ACTIVE = 'active'
    DONE = 'done'
    CLOSED = 'closed'
    FAILED = 'failed'

class RecurrencePattern(enum.Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    # CUSTOM = 'custom'

class Todo(Base):
    __tablename__ = 'todos'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    text = Column(String)
    importance = Column(Enum(Importance))
    deadline = Column(DateTime, nullable=True)
    reminder_minutes = Column(Integer, default=60)
    reminder_sent = Column(Boolean, default=False)  # New field
    status = Column(Enum(TodoStatus), default=TodoStatus.ACTIVE)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(Enum(RecurrencePattern), nullable=True)
    # recurrence_interval = Column(Integer, nullable=True)  # For custom intervals in days
    parent_id = Column(Integer, ForeignKey('todos.id'), nullable=True)


engine = create_engine('sqlite:///todos.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

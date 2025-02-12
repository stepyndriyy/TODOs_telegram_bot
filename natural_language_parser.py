from datetime import datetime, timedelta
import re
from models import Importance, RecurrencePattern
import pymorphy2

class TodoParser:
    def __init__(self):
        self.morph = pymorphy2.MorphAnalyzer()
        
        # Base time units and their variations
        self.time_units = {
            'минута': {'minutes': 1},
            'минуточка': {'minutes': 1},
            'час': {'hours': 1},
            'часик': {'hours': 1},
            'день': {'days': 1},
            'денёк': {'days': 1},
            'неделя': {'days': 7},
            'неделька': {'days': 7},
            'месяц': {'days': 30},
        }
        
        # Time shortcuts
        self.time_shortcuts = {
            'полчаса': timedelta(minutes=30),
            'полчасика': timedelta(minutes=30),
            'пол часа': timedelta(minutes=30),
            'пол часика': timedelta(minutes=30),
            'пол час': timedelta(minutes=30)
        }
        
        # Weekdays with variations
        self.weekdays = {
            'понедельник': 0, 'пн': 0,
            'вторник': 1, 'вт': 1,
            'среда': 2, 'ср': 2,
            'четверг': 3, 'чт': 3,
            'пятница': 4, 'пт': 4,
            'суббота': 5, 'сб': 5,
            'воскресенье': 6, 'вс': 6
        }
        
        # Time of day references
        self.time_of_day = {
            'утро': 9,
            'утром': 9,
            'утречком': 9,
            'день': 14,
            'днём': 14,
            'вечер': 19,
            'вечером': 19,
            'ночь': 23,
            'ночью': 23
        }

        self.day_markers = {
            'сегодня': 0,
            'завтра': 1,
            'послезавтра': 2,
            'позавчера': -2,
            'вчера': -1,
            'следующий': 7,
            'через день': 2,
            'через два дня': 3
        }

    def normalize_text(self, text: str) -> str:
        words = text.lower().split()
        normalized = []
        for word in words:
            parsed = self.morph.parse(word)[0]
            normalized.append(parsed.normal_form)
        return ' '.join(normalized)

    def parse_relative_time(self, text: str) -> tuple[datetime, str]:
        now = datetime.now()
        normalized = self.normalize_text(text)

        # Check day markers first
        for marker, days in self.day_markers.items():
            if marker in normalized:
                return now + timedelta(days=days), text.replace(marker, '').strip()
            
        # Check shortcuts first
        for shortcut, delta in self.time_shortcuts.items():
            if shortcut in normalized:
                return now + delta, re.sub(shortcut, '', text).strip()
        
        # Parse number + time unit patterns
        number_pattern = r'(?:через\s+)?(\d+)\s+(\w+)'
        matches = re.finditer(number_pattern, normalized)
        
        for match in matches:
            number, unit = match.groups()
            unit_normal = self.morph.parse(unit)[0].normal_form
            
            if unit_normal in self.time_units:
                delta_args = {k: v * int(number) for k, v in self.time_units[unit_normal].items()}
                return now + timedelta(**delta_args), re.sub(match.group(), '', text).strip()
        
        return now, text

    def parse_specific_time(self, text: str, base_date: datetime) -> tuple[datetime, str]:
        normalized = self.normalize_text(text)
        
        # Parse exact time patterns (15:00, в 15, etc)
        time_patterns = [
            (r'в (\d{1,2})(?::(\d{2}))?', lambda h, m: (int(h), int(m) if m else 0)),
            (r'(\d{1,2}):(\d{2})', lambda h, m: (int(h), int(m))),
        ]
        
        for pattern, time_func in time_patterns:
            match = re.search(pattern, text)
            if match:
                hour, minute = time_func(*match.groups())
                return base_date.replace(hour=hour, minute=minute), re.sub(pattern, '', text).strip()
        
        # Check time of day references
        for tod, hour in self.time_of_day.items():
            if tod in normalized:
                return base_date.replace(hour=hour, minute=0), text.replace(tod, '').strip()
        
        return base_date, text

    def parse_recurrence(self, text: str) -> tuple[bool, RecurrencePattern, str]:
        normalized = self.normalize_text(text)
        
        patterns = {
            r'кажд(?:ый|ую|ое)\s+(\w+)': RecurrencePattern.DAILY,
            r'раз в\s+(\w+)': RecurrencePattern.DAILY,
            r'по\s+(\w+)': RecurrencePattern.DAILY
        }
        
        for pattern, base_pattern in patterns.items():
            match = re.search(pattern, normalized)
            if match:
                unit = match.group(1)
                unit_normal = self.morph.parse(unit)[0].normal_form
                
                if unit_normal == 'день':
                    pattern = RecurrencePattern.DAILY
                elif unit_normal == 'неделя':
                    pattern = RecurrencePattern.WEEKLY
                elif unit_normal == 'месяц':
                    pattern = RecurrencePattern.MONTHLY
                    
                return True, pattern, re.sub(pattern, '', text).strip()
        
        return False, None, text

    def parse_reminder(self, text: str) -> tuple[int, str]:
        normalized = self.normalize_text(text)
        
        reminder_patterns = [
            (r'напомни (?:за|через) (\d+)\s+(\w+)', lambda n, u: int(n) * (60 if u.startswith('час') else 1)),
            (r'напомни за полчаса', lambda: 30),
            (r'напомни за час', lambda: 60),
        ]
        
        for pattern, reminder_func in reminder_patterns:
            match = re.search(pattern, normalized)
            if match:
                if len(match.groups()) == 2:
                    minutes = reminder_func(*match.groups())
                else:
                    minutes = reminder_func()
                return minutes, re.sub(pattern, '', text).strip()
        
        return 30, text  # Default 30 minutes

    def parse_todo(self, text: str):
        result = {
            'text': text,
            'importance': Importance.MEDIUM,
            'deadline': datetime.now().replace(hour=23, minute=59),
            'reminder_minutes': 30,
            'is_recurring': False,
            'recurrence_pattern': None
        }
        print(self.normalize_text(text))
        
        # Parse relative time first
        deadline, text = self.parse_relative_time(text)
        result['deadline'] = deadline
        
        # Then specific time
        deadline, text = self.parse_specific_time(text, result['deadline'])
        result['deadline'] = deadline
        
        # Parse recurrence
        is_recurring, pattern, text = self.parse_recurrence(text)
        result['is_recurring'] = is_recurring
        result['recurrence_pattern'] = pattern
        
        # Parse reminder
        reminder_minutes, text = self.parse_reminder(text)
        result['reminder_minutes'] = reminder_minutes
        
        # Clean up final text
        result['text'] = text.strip()
        
        return result

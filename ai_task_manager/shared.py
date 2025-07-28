from ai_task_manager.azure_openai import ask_openai
import json
from datetime import datetime, timedelta
import sqlite3
import os
from typing import Dict, List, Any, Optional

# In-memory data structures
tasks = []
budget_entries = []
schedule_events = []
chat_history = []

# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), 'assistant_data.db')

def init_database():
    """Initialize SQLite database for persistent storage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            deadline TEXT,
            category TEXT,
            priority INTEGER DEFAULT 1,
            done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    # Budget entries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Schedule events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            location TEXT,
            reminder_minutes INTEGER DEFAULT 15,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def load_data_from_db():
    """Load all data from database into memory"""
    global tasks, budget_entries, schedule_events, chat_history
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Load tasks
    cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
    tasks_data = cursor.fetchall()
    tasks = []
    for row in tasks_data:
        tasks.append({
            'id': row[0],
            'task': row[1],
            'deadline': row[2],
            'category': row[3],
            'priority': row[4],
            'done': bool(row[5]),
            'created_at': row[6],
            'completed_at': row[7]
        })
    
    # Load budget entries
    cursor.execute('SELECT * FROM budget_entries ORDER BY date DESC')
    budget_data = cursor.fetchall()
    budget_entries = []
    for row in budget_data:
        budget_entries.append({
            'id': row[0],
            'description': row[1],
            'amount': row[2],
            'category': row[3],
            'type': row[4],
            'date': row[5],
            'created_at': row[6]
        })
    
    # Load schedule events
    cursor.execute('SELECT * FROM schedule_events ORDER BY start_time ASC')
    schedule_data = cursor.fetchall()
    schedule_events = []
    for row in schedule_data:
        schedule_events.append({
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'start_time': row[3],
            'end_time': row[4],
            'location': row[5],
            'reminder_minutes': row[6],
            'created_at': row[7]
        })
    
    # Load recent chat history (last 50 messages)
    cursor.execute('SELECT role, content, timestamp FROM chat_history ORDER BY timestamp DESC LIMIT 50')
    chat_data = cursor.fetchall()
    chat_history = []
    for row in reversed(chat_data):  # Reverse to get chronological order
        chat_history.append({
            'role': row[0],
            'content': row[1],
            'timestamp': row[2]
        })
    
    conn.close()

# Initialize database and load data
init_database()
load_data_from_db()

def parse_llm_task(nl_input):
    """Enhanced task parsing with priority detection"""
    prompt = (
        "Extract the following from the user's input as JSON:\n"
        "- task: the main task description\n"
        "- deadline: (if any, format as YYYY-MM-DD, else null)\n"
        "- category: (if any, else null)\n"
        "- priority: (1=low, 2=medium, 3=high, 4=urgent, default=1)\n"
        "User input: \"{}\"\n"
        "Respond with a JSON object only."
    ).format(nl_input)
    
    try:
        llm_response = ask_openai(prompt, max_tokens=150)
        data = json.loads(llm_response)
        task_data = {
            "task": data.get("task", nl_input),
            "deadline": data.get("deadline"),
            "category": data.get("category"),
            "priority": data.get("priority", 1),
            "done": False,
            "created_at": datetime.now().isoformat()
        }
        
        # Save to database
        save_task_to_db(task_data)
        return task_data
    except Exception as e:
        # Fallback: just use the raw input
        task_data = {
            "task": nl_input, 
            "deadline": None, 
            "category": None, 
            "priority": 1,
            "done": False,
            "created_at": datetime.now().isoformat()
        }
        save_task_to_db(task_data)
        return task_data

def save_task_to_db(task_data):
    """Save task to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (task, deadline, category, priority, done, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        task_data['task'],
        task_data['deadline'],
        task_data['category'],
        task_data['priority'],
        task_data['done'],
        task_data['created_at']
    ))
    task_data['id'] = cursor.lastrowid
    conn.commit()
    conn.close()

def update_task_in_db(task_id, **updates):
    """Update task in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [task_id]
    
    cursor.execute(f'UPDATE tasks SET {set_clause} WHERE id = ?', values)
    conn.commit()
    conn.close()

def delete_task_from_db(task_id):
    """Delete task from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

def parse_budget_entry(nl_input):
    """Parse budget entry from natural language"""
    prompt = (
        "Extract budget information from the user's input as JSON:\n"
        "- description: what the money was for\n"
        "- amount: numeric amount (positive number)\n"
        "- category: (food, transport, entertainment, utilities, salary, etc.)\n"
        "- type: 'income' or 'expense'\n"
        "- date: today's date as YYYY-MM-DD\n"
        "User input: \"{}\"\n"
        "Respond with a JSON object only."
    ).format(nl_input)
    
    try:
        llm_response = ask_openai(prompt, max_tokens=150)
        data = json.loads(llm_response)
        budget_data = {
            "description": data.get("description", nl_input),
            "amount": abs(float(data.get("amount", 0))),
            "category": data.get("category", "other"),
            "type": data.get("type", "expense"),
            "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
            "created_at": datetime.now().isoformat()
        }
        
        # Save to database
        save_budget_entry_to_db(budget_data)
        return budget_data
    except Exception as e:
        return None

def save_budget_entry_to_db(budget_data):
    """Save budget entry to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO budget_entries (description, amount, category, type, date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        budget_data['description'],
        budget_data['amount'],
        budget_data['category'],
        budget_data['type'],
        budget_data['date'],
        budget_data['created_at']
    ))
    budget_data['id'] = cursor.lastrowid
    conn.commit()
    conn.close()

def parse_schedule_event(nl_input):
    """Parse schedule event from natural language"""
    prompt = (
        "Extract event information from the user's input as JSON:\n"
        "- title: event name\n"
        "- description: additional details (if any)\n"
        "- start_time: start time as YYYY-MM-DD HH:MM\n"
        "- end_time: end time as YYYY-MM-DD HH:MM (if mentioned)\n"
        "- location: where the event is (if mentioned)\n"
        "- reminder_minutes: minutes before to remind (default 15)\n"
        "User input: \"{}\"\n"
        "Respond with a JSON object only."
    ).format(nl_input)
    
    try:
        llm_response = ask_openai(prompt, max_tokens=200)
        data = json.loads(llm_response)
        event_data = {
            "title": data.get("title", nl_input),
            "description": data.get("description", ""),
            "start_time": data.get("start_time"),
            "end_time": data.get("end_time"),
            "location": data.get("location", ""),
            "reminder_minutes": data.get("reminder_minutes", 15),
            "created_at": datetime.now().isoformat()
        }
        
        # Save to database
        save_schedule_event_to_db(event_data)
        return event_data
    except Exception as e:
        return None

def save_schedule_event_to_db(event_data):
    """Save schedule event to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO schedule_events (title, description, start_time, end_time, location, reminder_minutes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        event_data['title'],
        event_data['description'],
        event_data['start_time'],
        event_data['end_time'],
        event_data['location'],
        event_data['reminder_minutes'],
        event_data['created_at']
    ))
    event_data['id'] = cursor.lastrowid
    conn.commit()
    conn.close()

def get_budget_summary():
    """Get budget summary for current month"""
    current_month = datetime.now().strftime("%Y-%m")
    
    total_income = sum(entry['amount'] for entry in budget_entries 
                      if entry['type'] == 'income' and entry['date'].startswith(current_month))
    total_expenses = sum(entry['amount'] for entry in budget_entries 
                        if entry['type'] == 'expense' and entry['date'].startswith(current_month))
    
    balance = total_income - total_expenses
    
    # Category breakdown
    expense_categories = {}
    for entry in budget_entries:
        if entry['type'] == 'expense' and entry['date'].startswith(current_month):
            category = entry['category']
            expense_categories[category] = expense_categories.get(category, 0) + entry['amount']
    
    return {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': balance,
        'expense_categories': expense_categories
    }

def get_upcoming_events(days=7):
    """Get upcoming events for the next N days"""
    now = datetime.now()
    future_date = now + timedelta(days=days)
    
    upcoming = []
    for event in schedule_events:
        try:
            event_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
            if now <= event_time <= future_date:
                upcoming.append(event)
        except:
            continue
    
    return sorted(upcoming, key=lambda x: x['start_time'])

def save_chat_message(role, content):
    """Save chat message to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_history (role, content, timestamp)
        VALUES (?, ?, ?)
    ''', (role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Add to memory
    chat_history.append({
        'role': role,
        'content': content,
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only last 100 messages in memory
    if len(chat_history) > 100:
        chat_history.pop(0)

def chat_with_assistant(user_input, context_data=None):
    """Enhanced chat with context awareness"""
    if context_data is None:
        context_data = {}
    
    # Build context-aware prompt
    prompt = """You are Moses, a sophisticated AI personal assistant. You help with:
- Task management and productivity
- Budget tracking and financial advice
- Schedule management and reminders
- General conversation and support

Current context:"""
    
    # Add task context
    if tasks:
        pending_tasks = [t for t in tasks if not t['done']]
        if pending_tasks:
            prompt += f"\nPending tasks: {len(pending_tasks)} tasks"
            high_priority = [t for t in pending_tasks if t.get('priority', 1) >= 3]
            if high_priority:
                prompt += f" ({len(high_priority)} high priority)"
    
    # Add budget context
    if budget_entries:
        summary = get_budget_summary()
        prompt += f"\nBudget this month: Income ${summary['total_income']:.2f}, Expenses ${summary['total_expenses']:.2f}, Balance ${summary['balance']:.2f}"
    
    # Add schedule context
    upcoming = get_upcoming_events(3)
    if upcoming:
        prompt += f"\nUpcoming events: {len(upcoming)} in next 3 days"
    
    # Add recent chat history for context
    recent_history = chat_history[-5:] if len(chat_history) > 5 else chat_history
    if recent_history:
        prompt += "\n\nRecent conversation:"
        for msg in recent_history:
            prompt += f"\n{msg['role'].capitalize()}: {msg['content']}"
    
    prompt += f"\n\nUser: {user_input}\nMoses:"
    
    try:
        ai_response = ask_openai(prompt, max_tokens=300, temperature=0.7)
        
        # Save conversation to history
        save_chat_message("user", user_input)
        save_chat_message("assistant", ai_response)
        
        return ai_response
    except Exception as e:
        return f"I'm having trouble connecting right now. Error: {str(e)}"

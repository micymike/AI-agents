import sys
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTextEdit, QLabel, QListWidget, QLineEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QDateEdit,
    QTimeEdit, QTextBrowser, QSplitter, QFrame, QGroupBox, QProgressBar,
    QSystemTrayIcon, QMenu, QAction, QMessageBox, QDialog, QDialogButtonBox,
    QFormLayout, QDoubleSpinBox, QCalendarWidget, QScrollArea, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QDate, QTime, QDateTime
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QPixmap, QPainter
import speech_recognition as sr
import threading
import asyncio
import edge_tts
import tempfile
import sounddevice as sd
import soundfile as sf
import pygame
import requests
import tempfile
import shutil
import subprocess

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from ai_task_manager.shared import (
        tasks, budget_entries, schedule_events, chat_history,
        parse_llm_task, parse_budget_entry, parse_schedule_event,
        chat_with_assistant, get_budget_summary, get_upcoming_events,
        save_chat_message, update_task_in_db, delete_task_from_db,
        load_data_from_db
    )
except ImportError:
    from shared import (
        tasks, budget_entries, schedule_events, chat_history,
        parse_llm_task, parse_budget_entry, parse_schedule_event,
        chat_with_assistant, get_budget_summary, get_upcoming_events,
        save_chat_message, update_task_in_db, delete_task_from_db,
        load_data_from_db
    )

class WakeWordListenerThread(QThread):
    wake_word_detected = pyqtSignal()
    debug_text = pyqtSignal(str)

    def __init__(self, wake_word="moses"):
        super().__init__()
        self.wake_word = wake_word.lower()
        self.running = True

    def run(self):
        recognizer = sr.Recognizer()
        try:
            mic = sr.Microphone()
        except Exception as e:
            self.debug_text.emit(f"Could not access microphone: {e}")
            return
            
        while self.running:
            with mic as source:
                try:
                    audio = recognizer.listen(source, timeout=2, phrase_time_limit=4)
                    try:
                        text = recognizer.recognize_google(audio).lower()
                        if self.wake_word in text:
                            self.wake_word_detected.emit()
                    except (sr.UnknownValueError, sr.RequestError):
                        continue
                except sr.WaitTimeoutError:
                    continue

    def stop(self):
        self.running = False

class SpeechRecognitionThread(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def run(self):
        recognizer = sr.Recognizer()
        try:
            mic = sr.Microphone()
            with mic as source:
                self.result.emit("🎤 Listening...")
                audio = recognizer.listen(source, timeout=5)
                self.result.emit("🔄 Processing...")
                text = recognizer.recognize_google(audio)
                self.result.emit(text)
        except sr.WaitTimeoutError:
            self.error.emit("⏰ No speech detected (timeout)")
        except sr.UnknownValueError:
            self.error.emit("❌ Could not understand audio")
        except sr.RequestError as e:
            self.error.emit(f"🚫 Speech recognition error: {e}")

class BudgetChartWidget(QWidget):
    
    def __init__(self):
        super().__init__()
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(10, 6))
            self.canvas = FigureCanvas(self.figure)
            layout = QVBoxLayout()
            layout.addWidget(self.canvas)
            self.setLayout(layout)
            self.update_chart()
        else:
            layout = QVBoxLayout()
            label = QLabel("📊 Chart visualization requires matplotlib\nInstall with: pip install matplotlib")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #666; font-size: 14px; padding: 50px;")
            layout.addWidget(label)
            self.setLayout(layout)

    def update_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            return
            
        self.figure.clear()
        
        if not budget_entries:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No budget data available', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        summary = get_budget_summary()
        
        # Create subplots
        ax1 = self.figure.add_subplot(221)  # Income vs Expenses
        ax2 = self.figure.add_subplot(222)  # Category breakdown
        ax3 = self.figure.add_subplot(223)  # Monthly trend
        ax4 = self.figure.add_subplot(224)  # Balance

        # Income vs Expenses pie chart
        if summary['total_income'] > 0 or summary['total_expenses'] > 0:
            ax1.pie([summary['total_income'], summary['total_expenses']], 
                   labels=['Income', 'Expenses'], 
                   colors=['#2ecc71', '#e74c3c'],
                   autopct='%1.1f%%')
            ax1.set_title('Income vs Expenses')

        # Category breakdown
        if summary['expense_categories']:
            categories = list(summary['expense_categories'].keys())
            amounts = list(summary['expense_categories'].values())
            ax2.bar(categories, amounts, color='#3498db')
            ax2.set_title('Expenses by Category')
            ax2.tick_params(axis='x', rotation=45)

        # Balance indicator
        balance = summary['balance']
        color = '#2ecc71' if balance >= 0 else '#e74c3c'
        ax4.bar(['Balance'], [balance], color=color)
        ax4.set_title(f'Current Balance: ${balance:.2f}')
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)

        self.figure.tight_layout()
        self.canvas.draw()

class TaskDialog(QDialog):
    def __init__(self, task_data=None, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.setWindowTitle("Add/Edit Task")
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout()

        self.task_edit = QLineEdit()
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(['Work', 'Personal', 'Health', 'Finance', 'Learning', 'Other'])
        
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(['Low (1)', 'Medium (2)', 'High (3)', 'Urgent (4)'])
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setDate(QDate.currentDate().addDays(1))
        self.deadline_edit.setCalendarPopup(True)

        if self.task_data:
            self.task_edit.setText(self.task_data.get('task', ''))
            if self.task_data.get('category'):
                self.category_combo.setCurrentText(self.task_data['category'])
            self.priority_combo.setCurrentIndex(self.task_data.get('priority', 1) - 1)
            if self.task_data.get('deadline'):
                date = QDate.fromString(self.task_data['deadline'], 'yyyy-MM-dd')
                self.deadline_edit.setDate(date)

        layout.addRow("Task:", self.task_edit)
        layout.addRow("Category:", self.category_combo)
        layout.addRow("Priority:", self.priority_combo)
        layout.addRow("Deadline:", self.deadline_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_task_data(self):
        return {
            'task': self.task_edit.text(),
            'category': self.category_combo.currentText(),
            'priority': self.priority_combo.currentIndex() + 1,
            'deadline': self.deadline_edit.date().toString('yyyy-MM-dd'),
            'done': False
        }

class BudgetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Budget Entry")
        self.setModal(True)
        self.resize(350, 250)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout()

        self.description_edit = QLineEdit()
        self.amount_edit = QDoubleSpinBox()
        self.amount_edit.setRange(0, 999999)
        self.amount_edit.setDecimals(2)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(['Expense', 'Income'])
        
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems([
            'Food', 'Transport', 'Entertainment', 'Utilities', 'Healthcare',
            'Shopping', 'Education', 'Salary', 'Investment', 'Other'
        ])
        
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)

        layout.addRow("Description:", self.description_edit)
        layout.addRow("Amount:", self.amount_edit)
        layout.addRow("Type:", self.type_combo)
        layout.addRow("Category:", self.category_combo)
        layout.addRow("Date:", self.date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_budget_data(self):
        return {
            'description': self.description_edit.text(),
            'amount': self.amount_edit.value(),
            'type': self.type_combo.currentText().lower(),
            'category': self.category_combo.currentText(),
            'date': self.date_edit.date().toString('yyyy-MM-dd')
        }

class ScheduleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Schedule Event")
        self.setModal(True)
        self.resize(400, 350)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout()

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setTime(QTime.currentTime())
        
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setTime(QTime.currentTime().addSecs(3600))  # +1 hour
        
        self.location_edit = QLineEdit()
        
        self.reminder_spin = QSpinBox()
        self.reminder_spin.setRange(0, 1440)  # 0 to 24 hours
        self.reminder_spin.setValue(15)
        self.reminder_spin.setSuffix(" minutes")

        layout.addRow("Title:", self.title_edit)
        layout.addRow("Description:", self.description_edit)
        layout.addRow("Date:", self.start_date_edit)
        layout.addRow("Start Time:", self.start_time_edit)
        layout.addRow("End Time:", self.end_time_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow("Reminder:", self.reminder_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_event_data(self):
        start_datetime = QDateTime(self.start_date_edit.date(), self.start_time_edit.time())
        end_datetime = QDateTime(self.start_date_edit.date(), self.end_time_edit.time())
        
        return {
            'title': self.title_edit.text(),
            'description': self.description_edit.toPlainText(),
            'start_time': start_datetime.toString('yyyy-MM-dd hh:mm'),
            'end_time': end_datetime.toString('yyyy-MM-dd hh:mm'),
            'location': self.location_edit.text(),
            'reminder_minutes': self.reminder_spin.value()
        }

class ModernAssistantGUI(QMainWindow):
    UPDATE_URL = "https://your-server.com/assistant/version.json"  # <-- Set this to your version.json URL

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Moses - AI Personal Assistant")
        self.setGeometry(100, 100, 1400, 900)
        self.is_awake = False
        self.is_muted = False

        # Set app icon if available
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Initialize pygame for TTS
        pygame.mixer.init()
        
        # Setup UI
        self.setup_ui()
        self.setup_timers()

        # Check for updates (after UI is initialized)
        self.check_for_updates()
        
        # Start wake word listener
        self.start_wake_word_listener()
        
        # Load initial data
        self.refresh_all_data()

    def setup_ui(self):
        """Setup the main UI with modern styling"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Apply modern styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background-color: white;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #007bff;
                color: white;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #007bff;
            }
            QListWidget, QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Left sidebar for status and quick actions
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar, 0)
        
        # Main content area with tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_chat_tab(), "💬 Chat")
        self.tab_widget.addTab(self.create_tasks_tab(), "✅ Tasks")
        self.tab_widget.addTab(self.create_budget_tab(), "💰 Budget")
        self.tab_widget.addTab(self.create_schedule_tab(), "📅 Schedule")
        self.tab_widget.addTab(self.create_analytics_tab(), "📊 Analytics")
        
        main_layout.addWidget(self.tab_widget, 1)
        
        central_widget.setLayout(main_layout)

    def create_sidebar(self):
        """Create the left sidebar with status and controls"""
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setFrameStyle(QFrame.StyledPanel)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #343a40;
                border-radius: 10px;
                margin: 5px;
            }
            QLabel {
                color: white;
                font-weight: bold;
            }
            QPushButton {
                background-color: #495057;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #6c757d;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Status section
        status_group = QGroupBox("🤖 Assistant Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("😴 Sleeping")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; padding: 10px;")
        status_layout.addWidget(self.status_label)
        
        # Control buttons
        btn_layout = QVBoxLayout()
        self.wake_btn = QPushButton("🌅 Wake Up")
        self.sleep_btn = QPushButton("😴 Sleep")
        self.mute_btn = QPushButton("🔇 Mute")
        self.record_btn = QPushButton("🎤 Voice Input")
        
        for btn in [self.wake_btn, self.sleep_btn, self.mute_btn, self.record_btn]:
            btn_layout.addWidget(btn)
        
        status_layout.addLayout(btn_layout)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Quick stats
        stats_group = QGroupBox("📈 Quick Stats")
        stats_layout = QVBoxLayout()
        
        self.tasks_stat = QLabel("Tasks: Loading...")
        self.budget_stat = QLabel("Balance: Loading...")
        self.events_stat = QLabel("Events: Loading...")
        
        for stat in [self.tasks_stat, self.budget_stat, self.events_stat]:
            stat.setStyleSheet("padding: 5px;")
            stats_layout.addWidget(stat)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Quick actions
        actions_group = QGroupBox("⚡ Quick Actions")
        actions_layout = QVBoxLayout()
        
        self.quick_task_btn = QPushButton("➕ Add Task")
        self.quick_budget_btn = QPushButton("💸 Add Expense")
        self.quick_event_btn = QPushButton("📅 Add Event")
        
        for btn in [self.quick_task_btn, self.quick_budget_btn, self.quick_event_btn]:
            actions_layout.addWidget(btn)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        layout.addStretch()
        sidebar.setLayout(layout)
        
        # Connect signals
        self.wake_btn.clicked.connect(self.wake_up)
        self.sleep_btn.clicked.connect(self.go_to_sleep)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.record_btn.clicked.connect(self.start_voice_recording)
        self.quick_task_btn.clicked.connect(self.quick_add_task)
        self.quick_budget_btn.clicked.connect(self.quick_add_budget)
        self.quick_event_btn.clicked.connect(self.quick_add_event)
        
        return sidebar

    def create_chat_tab(self):
        """Create the chat interface tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Chat display
        self.chat_display = QTextBrowser()
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message here...")
        self.send_btn = QPushButton("Send")
        self.clear_chat_btn = QPushButton("Clear")
        
        input_layout.addWidget(self.chat_input, 1)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.clear_chat_btn)
        
        layout.addLayout(input_layout)
        
        # Connect signals
        self.chat_input.returnPressed.connect(self.send_chat_message)
        self.send_btn.clicked.connect(self.send_chat_message)
        self.clear_chat_btn.clicked.connect(self.clear_chat)
        
        widget.setLayout(layout)
        return widget

    def create_tasks_tab(self):
        """Create the tasks management tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Tasks header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("📋 Task Management"))
        header_layout.addStretch()
        
        self.add_task_btn = QPushButton("➕ Add Task")
        self.edit_task_btn = QPushButton("✏️ Edit")
        self.complete_task_btn = QPushButton("✅ Complete")
        self.delete_task_btn = QPushButton("🗑️ Delete")
        
        for btn in [self.add_task_btn, self.edit_task_btn, self.complete_task_btn, self.delete_task_btn]:
            header_layout.addWidget(btn)
        
        layout.addLayout(header_layout)
        
        # Tasks table
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(6)
        self.tasks_table.setHorizontalHeaderLabels([
            "Status", "Task", "Category", "Priority", "Deadline", "Created"
        ])
        self.tasks_table.setAlternatingRowColors(True)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.tasks_table)
        
        # Quick add
        quick_layout = QHBoxLayout()
        self.quick_task_input = QLineEdit()
        self.quick_task_input.setPlaceholderText("Quick add task...")
        self.quick_add_task_btn = QPushButton("Add")
        
        quick_layout.addWidget(QLabel("Quick Add:"))
        quick_layout.addWidget(self.quick_task_input, 1)
        quick_layout.addWidget(self.quick_add_task_btn)
        
        layout.addLayout(quick_layout)
        
        # Connect signals
        self.add_task_btn.clicked.connect(self.add_task_dialog)
        self.edit_task_btn.clicked.connect(self.edit_task_dialog)
        self.complete_task_btn.clicked.connect(self.complete_selected_task)
        self.delete_task_btn.clicked.connect(self.delete_selected_task)
        self.quick_task_input.returnPressed.connect(self.quick_add_task_from_input)
        self.quick_add_task_btn.clicked.connect(self.quick_add_task_from_input)
        
        widget.setLayout(layout)
        return widget

    def create_budget_tab(self):
        """Create the budget management tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Budget header with summary
        header_layout = QHBoxLayout()
        self.budget_summary_label = QLabel("💰 Budget Summary: Loading...")
        self.budget_summary_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        header_layout.addWidget(self.budget_summary_label)
        header_layout.addStretch()
        
        self.add_budget_btn = QPushButton("➕ Add Entry")
        self.delete_budget_btn = QPushButton("🗑️ Delete")
        header_layout.addWidget(self.add_budget_btn)
        header_layout.addWidget(self.delete_budget_btn)
        
        layout.addLayout(header_layout)
        
        # Split view: table and chart
        splitter = QSplitter(Qt.Horizontal)
        
        # Budget entries table
        self.budget_table = QTableWidget()
        self.budget_table.setColumnCount(5)
        self.budget_table.setHorizontalHeaderLabels([
            "Date", "Description", "Category", "Type", "Amount"
        ])
        self.budget_table.setAlternatingRowColors(True)
        self.budget_table.setSelectionBehavior(QTableWidget.SelectRows)
        splitter.addWidget(self.budget_table)
        
        # Budget chart
        self.budget_chart = BudgetChartWidget()
        splitter.addWidget(self.budget_chart)
        
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        # Connect signals
        self.add_budget_btn.clicked.connect(self.add_budget_dialog)
        self.delete_budget_btn.clicked.connect(self.delete_selected_budget)
        
        widget.setLayout(layout)
        return widget

    def create_schedule_tab(self):
        """Create the schedule management tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Schedule header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("📅 Schedule Management"))
        header_layout.addStretch()
        
        self.add_event_btn = QPushButton("➕ Add Event")
        self.edit_event_btn = QPushButton("✏️ Edit")
        self.delete_event_btn = QPushButton("🗑️ Delete")
        
        for btn in [self.add_event_btn, self.edit_event_btn, self.delete_event_btn]:
            header_layout.addWidget(btn)
        
        layout.addLayout(header_layout)
        
        # Split view: calendar and events
        splitter = QSplitter(Qt.Horizontal)
        
        # Calendar widget
        calendar_widget = QWidget()
        calendar_layout = QVBoxLayout()
        
        self.calendar = QCalendarWidget()
        self.calendar.setStyleSheet("""
            QCalendarWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        calendar_layout.addWidget(self.calendar)
        
        # Upcoming events
        upcoming_group = QGroupBox("🔔 Upcoming Events")
        upcoming_layout = QVBoxLayout()
        self.upcoming_events_list = QListWidget()
        upcoming_layout.addWidget(self.upcoming_events_list)
        upcoming_group.setLayout(upcoming_layout)
        calendar_layout.addWidget(upcoming_group)
        
        calendar_widget.setLayout(calendar_layout)
        splitter.addWidget(calendar_widget)
        
        # Events table
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(5)
        self.events_table.setHorizontalHeaderLabels([
            "Title", "Date", "Time", "Location", "Reminder"
        ])
        self.events_table.setAlternatingRowColors(True)
        self.events_table.setSelectionBehavior(QTableWidget.SelectRows)
        splitter.addWidget(self.events_table)
        
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        # Connect signals
        self.add_event_btn.clicked.connect(self.add_event_dialog)
        self.edit_event_btn.clicked.connect(self.edit_event_dialog)
        self.delete_event_btn.clicked.connect(self.delete_selected_event)
        
        widget.setLayout(layout)
        return widget

    def create_analytics_tab(self):
        """Create the analytics and insights tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Analytics header
        header = QLabel("📊 Analytics & Insights")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Metrics cards
        metrics_layout = QHBoxLayout()
        
        # Task completion rate
        task_card = QGroupBox("✅ Task Completion")
        task_card_layout = QVBoxLayout()
        self.task_completion_label = QLabel("Loading...")
        self.task_completion_progress = QProgressBar()
        task_card_layout.addWidget(self.task_completion_label)
        task_card_layout.addWidget(self.task_completion_progress)
        task_card.setLayout(task_card_layout)
        
        # Budget health
        budget_card = QGroupBox("💰 Budget Health")
        budget_card_layout = QVBoxLayout()
        self.budget_health_label = QLabel("Loading...")
        self.budget_health_progress = QProgressBar()
        budget_card_layout.addWidget(self.budget_health_label)
        budget_card_layout.addWidget(self.budget_health_progress)
        budget_card.setLayout(budget_card_layout)
        
        # Productivity score
        productivity_card = QGroupBox("🚀 Productivity")
        productivity_card_layout = QVBoxLayout()
        self.productivity_label = QLabel("Loading...")
        self.productivity_progress = QProgressBar()
        productivity_card_layout.addWidget(self.productivity_label)
        productivity_card_layout.addWidget(self.productivity_progress)
        productivity_card.setLayout(productivity_card_layout)
        
        metrics_layout.addWidget(task_card)
        metrics_layout.addWidget(budget_card)
        metrics_layout.addWidget(productivity_card)
        layout.addLayout(metrics_layout)
        
        # Insights text area
        insights_group = QGroupBox("🧠 AI Insights")
        insights_layout = QVBoxLayout()
        self.insights_text = QTextBrowser()
        self.insights_text.setMaximumHeight(200)
        self.refresh_insights_btn = QPushButton("🔄 Refresh Insights")
        insights_layout.addWidget(self.insights_text)
        insights_layout.addWidget(self.refresh_insights_btn)
        insights_group.setLayout(insights_layout)
        layout.addWidget(insights_group)
        
        layout.addStretch()
        
        # Connect signals
        self.refresh_insights_btn.clicked.connect(self.generate_insights)
        
        widget.setLayout(layout)
        return widget

    def setup_timers(self):
        """Setup periodic timers for updates"""
        # Refresh data every 30 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_all_data)
        self.refresh_timer.start(30000)  # 30 seconds
        
        # Check for reminders every minute
        self.reminder_timer = QTimer()
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(60000)  # 1 minute

    def start_wake_word_listener(self):
        """Start the wake word detection thread"""
        try:
            self.wake_word_thread = WakeWordListenerThread(wake_word="moses")
            self.wake_word_thread.wake_word_detected.connect(self.on_wake_word_detected)
            self.wake_word_thread.debug_text.connect(self.add_debug_message)
            self.wake_word_thread.start()
            self.add_debug_message("🎤 Wake word listener started")
        except Exception as e:
            self.add_debug_message(f"❌ Error starting wake word listener: {e}")

    def wake_up(self):
        """Wake up the assistant"""
        self.is_awake = True
        self.status_label.setText("🤖 Awake & Ready")
        self.add_chat_message("Assistant", "Good day! How may I assist you today? 😊")
        self.speak("How may I assist you today?")

    def go_to_sleep(self):
        """Put the assistant to sleep"""
        self.is_awake = False
        self.status_label.setText("😴 Sleeping")
        self.add_chat_message("Assistant", "Going to sleep. Say 'Moses' to wake me up! 💤")
        self.speak("Going to sleep.")

    def toggle_mute(self):
        """Toggle mute state"""
        self.is_muted = not self.is_muted
        self.mute_btn.setText("🔊 Unmute" if self.is_muted else "🔇 Mute")
        status = "muted" if self.is_muted else "unmuted"
        self.add_debug_message(f"🔊 Audio {status}")

    def speak(self, text):
        """Text-to-speech functionality using edge-tts (Microsoft neural voices)"""
        if not self.is_muted:
            self.stop_speaking()
            def tts_worker():
                try:
                    voice = "en-US-JennyNeural"  # You can change to any supported voice
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                        temp_path = fp.name
                    # Synthesize speech to file using edge-tts
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        edge_tts.Communicate(text, voice).save(temp_path)
                    )
                    # Play the audio file using sounddevice
                    data, samplerate = sf.read(temp_path)
                    self._tts_playback = True
                    sd.play(data, samplerate)
                    sd.wait()
                    self._tts_playback = False
                except Exception as e:
                    self.add_debug_message(f"🔊 TTS Error: {e}")
                finally:
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            self._tts_thread = threading.Thread(target=tts_worker, daemon=True)
            self._tts_thread.start()

    def stop_speaking(self):
        """Interrupt TTS playback if speaking"""
        try:
            if hasattr(self, "_tts_playback") and self._tts_playback:
                sd.stop()
                self._tts_playback = False
        except Exception:
            pass
        if hasattr(self, "_tts_thread") and self._tts_thread.is_alive():
            # Thread will exit after playback is stopped
            pass

    def start_voice_recording(self):
        """Start voice input recording"""
        self.add_chat_message("System", "🎤 Listening for voice input...")
        self.sr_thread = SpeechRecognitionThread()
        self.sr_thread.result.connect(self.handle_speech_result)
        self.sr_thread.error.connect(self.handle_speech_error)
        self.sr_thread.start()

    def on_wake_word_detected(self):
        """Handle wake word detection"""
        if not self.is_awake:
            self.wake_up()
        self.start_voice_recording()

    def handle_speech_result(self, text):
        """Handle speech recognition result"""
        if text in ["🎤 Listening...", "🔄 Processing..."]:
            self.add_chat_message("System", text)
        else:
            self.add_chat_message("You (Voice)", text)
            if self.is_awake:
                self.process_voice_command(text)
            # Always-on voice: restart listening if awake and not muted
            if self.is_awake and not self.is_muted:
                QTimer.singleShot(500, self.start_voice_recording)

    def handle_speech_error(self, error_msg):
        """Handle speech recognition error"""
        self.add_chat_message("System", error_msg)
        # Always-on voice: restart listening if awake and not muted
        if self.is_awake and not self.is_muted:
            QTimer.singleShot(500, self.start_voice_recording)

    def process_voice_command(self, text):
        """Process voice commands with enhanced AI"""
        # Interrupt TTS if user speaks
        self.stop_speaking()
        text_lower = text.lower()
        
        # Check for specific commands first
        if "sleep" in text_lower:
            self.go_to_sleep()
        elif "wake" in text_lower:
            self.wake_up()
        elif "mute" in text_lower:
            self.toggle_mute()
        elif "clear chat" in text_lower:
            self.clear_chat()
        elif "add task" in text_lower:
            task_text = text_lower.replace("add task", "").strip()
            if task_text:
                self.add_task_from_text(task_text)
        elif "add expense" in text_lower or "spent" in text_lower:
            self.add_budget_from_text(text)
        elif "schedule" in text_lower or "appointment" in text_lower:
            self.add_event_from_text(text)
        else:
            # Use AI chat for general queries
            self.send_ai_message(text)

    def add_chat_message(self, sender, message):
        """Add message to chat display"""
        timestamp = datetime.now().strftime("%H:%M")
        if sender == "System":
            self.chat_display.append(f"<span style='color: #6c757d;'>[{timestamp}] <i>{message}</i></span>")
        elif sender == "Assistant":
            # Use mimo.jpg as the assistant's avatar, styled as a circle
            avatar_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mimo.jpg"))
            avatar_url = f"file:///{avatar_path.replace(os.sep, '/')}"
            self.chat_display.append(
                f"""
                <div style="display: flex; align-items: flex-start; margin-bottom: 8px;">
                    <img src="{avatar_url}" style="width:40px; height:40px; border-radius:50%; object-fit:cover; margin-right:12px; border:2px solid #007bff; box-shadow:0 2px 8px #007bff22;">
                    <div>
                        <span style='color: #007bff; font-weight:bold;'>[{timestamp}] Moses:</span>
                        <span style='color: #222;'>{message}</span>
                    </div>
                </div>
                """
            )
        else:
            self.chat_display.append(f"<span style='color: #28a745;'><b>[{timestamp}] {sender}:</b> {message}</span>")

    def add_debug_message(self, message):
        """Add debug message"""
        self.add_chat_message("System", message)

    def send_chat_message(self):
        """Send chat message"""
        message = self.chat_input.text().strip()
        if message:
            self.add_chat_message("You", message)
            self.chat_input.clear()
            
            if self.is_awake:
                self.send_ai_message(message)
            else:
                self.add_chat_message("Assistant", "I'm currently sleeping. Please wake me up first! 😴")

    def send_ai_message(self, message):
        """Send message to AI and get response"""
        try:
            response = chat_with_assistant(message)
            self.add_chat_message("Assistant", response)
            self.speak(response)
        except Exception as e:
            error_msg = f"Sorry, I'm having trouble connecting right now. Error: {str(e)}"
            self.add_chat_message("Assistant", error_msg)

    def clear_chat(self):
        """Clear chat display"""
        self.chat_display.clear()
        self.add_chat_message("System", "Chat cleared")

    def refresh_all_data(self):
        """Refresh all data displays"""
        load_data_from_db()
        self.refresh_tasks_table()
        self.refresh_budget_table()
        self.refresh_events_table()
        self.refresh_upcoming_events()
        self.update_sidebar_stats()
        self.update_analytics()
        if hasattr(self, 'budget_chart'):
            self.budget_chart.update_chart()

    def refresh_tasks_table(self):
        """Refresh the tasks table"""
        self.tasks_table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            status = "✅" if task.get('done') else "⏳"
            priority_map = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
            priority = priority_map.get(task.get('priority', 1), "Low")
            
            self.tasks_table.setItem(i, 0, QTableWidgetItem(status))
            self.tasks_table.setItem(i, 1, QTableWidgetItem(task.get('task', '')))
            self.tasks_table.setItem(i, 2, QTableWidgetItem(task.get('category', '')))
            self.tasks_table.setItem(i, 3, QTableWidgetItem(priority))
            self.tasks_table.setItem(i, 4, QTableWidgetItem(task.get('deadline', '')))
            self.tasks_table.setItem(i, 5, QTableWidgetItem(task.get('created_at', '')[:10]))

    def refresh_budget_table(self):
        """Refresh the budget table"""
        self.budget_table.setRowCount(len(budget_entries))
        for i, entry in enumerate(budget_entries):
            self.budget_table.setItem(i, 0, QTableWidgetItem(entry.get('date', '')))
            self.budget_table.setItem(i, 1, QTableWidgetItem(entry.get('description', '')))
            self.budget_table.setItem(i, 2, QTableWidgetItem(entry.get('category', '')))
            self.budget_table.setItem(i, 3, QTableWidgetItem(entry.get('type', '').title()))
            self.budget_table.setItem(i, 4, QTableWidgetItem(f"${entry.get('amount', 0):.2f}"))
        
        # Update budget summary
        summary = get_budget_summary()
        self.budget_summary_label.setText(
            f"💰 This Month - Income: ${summary['total_income']:.2f} | "
            f"Expenses: ${summary['total_expenses']:.2f} | "
            f"Balance: ${summary['balance']:.2f}"
        )

    def refresh_events_table(self):
        """Refresh the events table"""
        self.events_table.setRowCount(len(schedule_events))
        for i, event in enumerate(schedule_events):
            start_time = event.get('start_time', '')
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d')
                    time_str = dt.strftime('%H:%M')
                except:
                    date_str = start_time[:10]
                    time_str = start_time[11:16]
            else:
                date_str = time_str = ''
            
            self.events_table.setItem(i, 0, QTableWidgetItem(event.get('title', '')))
            self.events_table.setItem(i, 1, QTableWidgetItem(date_str))
            self.events_table.setItem(i, 2, QTableWidgetItem(time_str))
            self.events_table.setItem(i, 3, QTableWidgetItem(event.get('location', '')))
            self.events_table.setItem(i, 4, QTableWidgetItem(f"{event.get('reminder_minutes', 15)} min"))

    def refresh_upcoming_events(self):
        """Refresh upcoming events list"""
        self.upcoming_events_list.clear()
        upcoming = get_upcoming_events(7)
        for event in upcoming:
            try:
                dt = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                time_str = dt.strftime('%m/%d %H:%M')
                self.upcoming_events_list.addItem(f"{time_str} - {event['title']}")
            except:
                self.upcoming_events_list.addItem(f"{event['title']}")

    def update_sidebar_stats(self):
        """Update sidebar statistics"""
        pending_tasks = len([t for t in tasks if not t.get('done')])
        self.tasks_stat.setText(f"Tasks: {pending_tasks} pending")
        
        summary = get_budget_summary()
        self.budget_stat.setText(f"Balance: ${summary['balance']:.2f}")
        
        upcoming = get_upcoming_events(7)
        self.events_stat.setText(f"Events: {len(upcoming)} upcoming")

    def update_analytics(self):
        """Update analytics tab"""
        # Task completion rate
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.get('done')])
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        self.task_completion_label.setText(f"Completed: {completed_tasks}/{total_tasks} ({completion_rate:.1f}%)")
        self.task_completion_progress.setValue(int(completion_rate))
        
        # Budget health (positive balance = good)
        summary = get_budget_summary()
        budget_health = min(100, max(0, (summary['balance'] / max(summary['total_income'], 1)) * 100 + 50))
        self.budget_health_label.setText(f"Balance: ${summary['balance']:.2f}")
        self.budget_health_progress.setValue(int(budget_health))
        
        # Productivity score (based on tasks completed recently)
        recent_completed = len([t for t in tasks if t.get('done') and t.get('completed_at')])
        productivity_score = min(100, recent_completed * 10)
        self.productivity_label.setText(f"Recent Activity: {recent_completed} tasks")
        self.productivity_progress.setValue(productivity_score)

    def generate_insights(self):
        """Generate AI insights"""
        try:
            # Prepare data summary for AI
            task_summary = f"Tasks: {len(tasks)} total, {len([t for t in tasks if not t.get('done')])} pending"
            budget_summary = get_budget_summary()
            budget_text = f"Budget: ${budget_summary['balance']:.2f} balance this month"
            events_count = len(get_upcoming_events(7))
            
            prompt = f"""Based on this user data, provide 3-4 brief insights and suggestions:
{task_summary}
{budget_text}
Upcoming events: {events_count}

Focus on productivity, financial health, and time management. Be encouraging and specific."""
            
            insights = chat_with_assistant(prompt)
            self.insights_text.setHtml(f"<div style='padding: 10px;'>{insights}</div>")
        except Exception as e:
            self.insights_text.setText(f"Unable to generate insights: {e}")

    def check_reminders(self):
        """Check for event reminders"""
        now = datetime.now()
        for event in schedule_events:
            try:
                event_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                reminder_time = event_time - timedelta(minutes=event.get('reminder_minutes', 15))
                
                if reminder_time <= now <= reminder_time + timedelta(minutes=1):
                    self.show_reminder(event)
            except:
                continue

    def show_reminder(self, event):
        """Show event reminder"""
        msg = QMessageBox()
        msg.setWindowTitle("📅 Event Reminder")
        msg.setText(f"Upcoming Event: {event['title']}")
        msg.setInformativeText(f"Time: {event['start_time']}\nLocation: {event.get('location', 'Not specified')}")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
        
        self.speak(f"Reminder: {event['title']} is coming up soon")

    # Dialog methods
    def quick_add_task(self):
        """Quick add task dialog"""
        self.add_task_dialog()

    def quick_add_budget(self):
        """Quick add budget dialog"""
        self.add_budget_dialog()

    def quick_add_event(self):
        """Quick add event dialog"""
        self.add_event_dialog()

    def add_task_dialog(self):
        """Show add task dialog"""
        dialog = TaskDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            task_data = dialog.get_task_data()
            self.add_task_from_data(task_data)

    def edit_task_dialog(self):
        """Show edit task dialog"""
        row = self.tasks_table.currentRow()
        if row >= 0 and row < len(tasks):
            dialog = TaskDialog(tasks[row], parent=self)
            if dialog.exec_() == QDialog.Accepted:
                task_data = dialog.get_task_data()
                self.update_task(row, task_data)

    def add_budget_dialog(self):
        """Show add budget dialog"""
        dialog = BudgetDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            budget_data = dialog.get_budget_data()
            self.add_budget_from_data(budget_data)

    def add_event_dialog(self):
        """Show add event dialog"""
        dialog = ScheduleDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            event_data = dialog.get_event_data()
            self.add_event_from_data(event_data)

    def edit_event_dialog(self):
        """Show edit event dialog"""
        # Implementation for editing events
        pass

    # Data manipulation methods
    def add_task_from_text(self, text):
        """Add task from text input"""
        task_data = parse_llm_task(text)
        tasks.append(task_data)
        self.refresh_tasks_table()
        self.add_chat_message("System", f"✅ Task added: {task_data['task']}")

    def add_task_from_data(self, task_data):
        """Add task from dialog data"""
        task_obj = parse_llm_task(f"{task_data['task']} category:{task_data['category']} priority:{task_data['priority']} deadline:{task_data['deadline']}")
        tasks.append(task_obj)
        self.refresh_tasks_table()
        self.add_chat_message("System", f"✅ Task added: {task_obj['task']}")

    def quick_add_task_from_input(self):
        """Add task from quick input"""
        text = self.quick_task_input.text().strip()
        if text:
            self.add_task_from_text(text)
            self.quick_task_input.clear()

    def complete_selected_task(self):
        """Complete selected task"""
        row = self.tasks_table.currentRow()
        if row >= 0 and row < len(tasks):
            tasks[row]['done'] = True
            tasks[row]['completed_at'] = datetime.now().isoformat()
            if 'id' in tasks[row]:
                update_task_in_db(tasks[row]['id'], done=True, completed_at=tasks[row]['completed_at'])
            self.refresh_tasks_table()
            self.add_chat_message("System", f"✅ Task completed: {tasks[row]['task']}")

    def delete_selected_task(self):
        """Delete selected task"""
        row = self.tasks_table.currentRow()
        if row >= 0 and row < len(tasks):
            task = tasks.pop(row)
            if 'id' in task:
                delete_task_from_db(task['id'])
            self.refresh_tasks_table()
            self.add_chat_message("System", f"🗑️ Task deleted: {task['task']}")

    def update_task(self, row, task_data):
        """Update existing task"""
        if row >= 0 and row < len(tasks):
            tasks[row].update(task_data)
            if 'id' in tasks[row]:
                update_task_in_db(tasks[row]['id'], **task_data)
            self.refresh_tasks_table()
            self.add_chat_message("System", f"✏️ Task updated: {task_data['task']}")

    def add_budget_from_text(self, text):
        """Add budget entry from text"""
        budget_data = parse_budget_entry(text)
        if budget_data:
            budget_entries.append(budget_data)
            self.refresh_budget_table()
            self.budget_chart.update_chart()
            self.add_chat_message("System", f"💰 Budget entry added: {budget_data['description']}")

    def add_budget_from_data(self, budget_data):
        """Add budget entry from dialog data"""
        from shared import save_budget_entry_to_db
        save_budget_entry_to_db(budget_data)
        budget_entries.append(budget_data)
        self.refresh_budget_table()
        self.budget_chart.update_chart()
        self.add_chat_message("System", f"💰 Budget entry added: {budget_data['description']}")

    def delete_selected_budget(self):
        """Delete selected budget entry"""
        row = self.budget_table.currentRow()
        if row >= 0 and row < len(budget_entries):
            entry = budget_entries.pop(row)
            self.refresh_budget_table()
            self.budget_chart.update_chart()
            self.add_chat_message("System", f"🗑️ Budget entry deleted: {entry['description']}")

    def add_event_from_text(self, text):
        """Add event from text"""
        event_data = parse_schedule_event(text)
        if event_data:
            schedule_events.append(event_data)
            self.refresh_events_table()
            self.refresh_upcoming_events()
            self.add_chat_message("System", f"📅 Event added: {event_data['title']}")

    def add_event_from_data(self, event_data):
        """Add event from dialog data"""
        from shared import save_schedule_event_to_db
        save_schedule_event_to_db(event_data)
        schedule_events.append(event_data)
        self.refresh_events_table()
        self.refresh_upcoming_events()
        self.add_chat_message("System", f"📅 Event added: {event_data['title']}")

    def delete_selected_event(self):
        """Delete selected event"""
        row = self.events_table.currentRow()
        if row >= 0 and row < len(schedule_events):
            event = schedule_events.pop(row)
            self.refresh_events_table()
            self.refresh_upcoming_events()
            self.add_chat_message("System", f"🗑️ Event deleted: {event['title']}")

    def closeEvent(self, event):
        """Handle application close"""
        if hasattr(self, 'wake_word_thread'):
            self.wake_word_thread.stop()
            self.wake_word_thread.wait()
        event.accept()

    def check_for_updates(self):
        """Check for app updates from remote server"""
        try:
            resp = requests.get(self.UPDATE_URL, timeout=5)
            if resp.status_code != 200:
                return
            data = resp.json()
            latest_version = data.get("version")
            download_url = data.get("download_url")
            if not latest_version or not download_url:
                return
            current_version = "1.0.0"  # <-- Set your app version here
            if self.is_newer_version(latest_version, current_version):
                reply = QMessageBox.question(
                    self, "Update Available",
                    f"A new version ({latest_version}) is available. Download and install now?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.download_and_install_update(download_url)
        except Exception as e:
            self.add_debug_message(f"Update check failed: {e}")

    def is_newer_version(self, latest, current):
        """Compare semantic version strings"""
        def parse(v): return [int(x) for x in v.split(".")]
        return parse(latest) > parse(current)

    def download_and_install_update(self, url):
        """Download new exe and launch it"""
        try:
            self.add_debug_message("Downloading update...")
            r = requests.get(url, stream=True, timeout=30)
            if r.status_code != 200:
                self.add_debug_message("Failed to download update.")
                return
            with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as f:
                shutil.copyfileobj(r.raw, f)
                new_exe = f.name
            self.add_debug_message("Launching new version...")
            subprocess.Popen([new_exe])
            QMessageBox.information(self, "Update", "The new version will now launch. Please close this window.")
            QApplication.quit()
        except Exception as e:
            self.add_debug_message(f"Update failed: {e}")

# Keep the old class name for compatibility
AssistantGUI = ModernAssistantGUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Moses - AI Personal Assistant")
    
    # Set application style
    app.setStyle('Fusion')
    
    gui = ModernAssistantGUI()
    gui.show()
    
    sys.exit(app.exec_())

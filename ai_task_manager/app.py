import sys
from PyQt5.QtWidgets import QApplication
from assistant_gui import ModernAssistantGUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Moses - AI Personal Assistant")
    app.setApplicationVersion("2.0")
    
    # Set application style for modern look
    app.setStyle('Fusion')
    
    # Create and show the main window
    gui = ModernAssistantGUI()
    gui.show()
    
    # Add welcome message
    gui.add_chat_message("System", "🚀 Moses AI Assistant v2.0 loaded successfully!")
    gui.add_chat_message("Assistant", "Welcome! I'm your enhanced AI assistant with task management, budgeting, and scheduling capabilities. Say 'Moses' to wake me up or click the Wake Up button!")
    
    sys.exit(app.exec_())

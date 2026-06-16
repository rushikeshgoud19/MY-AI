import sys
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QLineEdit, QScrollArea, QFrame, QHBoxLayout,
    QStackedWidget, QPushButton, QListWidget, QProgressBar,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont, QCursor

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

class MainWindow(QMainWindow):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.initUI()
        self.setupBridge()

    def initUI(self):
        self.setWindowTitle("Mizune AI")
        self.resize(1000, 650)
        
        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        # Main container
        self.main_container = QFrame()
        self.main_container.setObjectName("MainContainer")
        self.main_container.setStyleSheet("""
            #MainContainer {
                background-color: #1e1e24;
            }
        """)

        # Horizontal layout for Sidebar + Content
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.setupSidebar()
        self.setupContentArea()

        self.setCentralWidget(self.main_container)

    def setupSidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #17171d;
                border-right: 1px solid #2a2a35;
            }
            QPushButton {
                background-color: transparent;
                color: #d0d0d0;
                border: none;
                text-align: left;
                padding: 12px 20px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 15px;
                font-weight: bold;
                border-radius: 6px;
                margin: 4px 10px;
            }
            QPushButton:hover {
                background-color: #2b2b36;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #3a2b58;
                color: #a777e3;
                border-left: 4px solid #a777e3;
            }
            QLabel#Logo {
                color: #a777e3;
                font-family: 'Segoe UI', sans-serif;
                font-size: 22px;
                font-weight: 900;
                padding: 20px 10px 30px 20px;
            }
        """)

        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if WEB_ENGINE_AVAILABLE:
            self.slime_view = QWebEngineView()
            self.slime_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            self.slime_view.setFixedSize(220, 160)
            self.slime_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
            slime_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "slime.html"))
            self.slime_view.setUrl(QUrl.fromLocalFile(slime_path))
            layout.addWidget(self.slime_view)
        else:
            logo = QLabel("✨ Mizune AI")
            logo.setObjectName("Logo")
            layout.addWidget(logo)

        # Navigation Buttons
        self.btn_chat = QPushButton("💬  Chat")
        self.btn_chat.setCheckable(True)
        self.btn_chat.setChecked(True)
        self.btn_chat.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_chat.clicked.connect(lambda: self.switch_tab(0))

        self.btn_memory = QPushButton("🧠  Memory Graph")
        self.btn_memory.setCheckable(True)
        self.btn_memory.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_memory.clicked.connect(lambda: self.switch_tab(1))

        self.btn_skills = QPushButton("⚡  Skills & Tools")
        self.btn_skills.setCheckable(True)
        self.btn_skills.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_skills.clicked.connect(lambda: self.switch_tab(2))

        self.btn_whatsapp = QPushButton("📱  WhatsApp")
        self.btn_whatsapp.setCheckable(True)
        self.btn_whatsapp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_whatsapp.clicked.connect(lambda: self.switch_tab(3))

        self.btn_kernel = QPushButton("🖥️  Kernel Stream")
        self.btn_kernel.setCheckable(True)
        self.btn_kernel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_kernel.clicked.connect(lambda: self.switch_tab(4))

        layout.addWidget(self.btn_chat)
        layout.addWidget(self.btn_memory)
        layout.addWidget(self.btn_skills)
        layout.addWidget(self.btn_whatsapp)
        layout.addWidget(self.btn_kernel)

        # Status Indicator at bottom of sidebar
        layout.addStretch()

        # Emotion Indicator
        emotion_frame = QFrame()
        emotion_layout = QVBoxLayout(emotion_frame)
        emotion_layout.setContentsMargins(20, 0, 20, 10)
        
        emotion_title_layout = QHBoxLayout()
        self.emotion_label = QLabel("Emotion: Neutral")
        self.emotion_label.setStyleSheet("color: #a0a0a0; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: bold; border: none;")
        emotion_title_layout.addWidget(self.emotion_label)
        emotion_title_layout.addStretch()
        
        self.emotion_bar = QProgressBar()
        self.emotion_bar.setFixedHeight(8)
        self.emotion_bar.setTextVisible(False)
        self.emotion_bar.setValue(50)  # Neutral is middle
        # Default styling
        self.emotion_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2b2b36;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a777e3, stop:1 #d4a5ff);
                border-radius: 4px;
            }
        """)
        
        emotion_layout.addLayout(emotion_title_layout)
        emotion_layout.addWidget(self.emotion_bar)
        layout.addWidget(emotion_frame)
        
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(20, 20, 20, 20)
        
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(12, 12)
        self.status_dot.setStyleSheet("background-color: #ff6b6b; border-radius: 6px;")
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #a0a0a0; font-family: 'Segoe UI', sans-serif; font-size: 13px; border: none;")
        
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        layout.addWidget(status_frame)

        self.main_layout.addWidget(self.sidebar)

        self.nav_buttons = [self.btn_chat, self.btn_memory, self.btn_skills, self.btn_whatsapp, self.btn_kernel]

    def switch_tab(self, index):
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
            
        # Refresh memory graph when opened
        if index == 1 and WEB_ENGINE_AVAILABLE:
            graph_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memory_graph.html"))
            if os.path.exists(graph_path):
                self.web_view.setUrl(QUrl.fromLocalFile(graph_path))

    def setupContentArea(self):
        self.stacked_widget = QStackedWidget()
        
        # --- TAB 0: CHAT ---
        self.chat_page = QWidget()
        chat_layout = QVBoxLayout(self.chat_page)
        chat_layout.setContentsMargins(20, 20, 20, 20)
        chat_layout.setSpacing(15)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #25252d;
                border: 1px solid #33333d;
                border-radius: 8px;
            }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #555; border-radius: 4px; }
        """)

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_inner_layout = QVBoxLayout(self.chat_container)
        self.chat_inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.chat_container)
        chat_layout.addWidget(self.scroll_area)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Message Mizune...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b36;
                color: white;
                border-radius: 8px;
                padding: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 15px;
                border: 1px solid #3a3a4a;
            }
            QLineEdit:focus {
                border: 1px solid #a777e3;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        chat_layout.addWidget(self.input_field)

        self.stacked_widget.addWidget(self.chat_page)

        # --- TAB 1: MEMORY GRAPH ---
        self.memory_page = QWidget()
        memory_layout = QVBoxLayout(self.memory_page)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        
        if WEB_ENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            memory_layout.addWidget(self.web_view)
        else:
            fallback = QLabel("PyQt6-WebEngine not installed.\nCannot render memory_graph.html natively.")
            fallback.setStyleSheet("color: white; font-size: 16px;")
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            memory_layout.addWidget(fallback)
            
        self.stacked_widget.addWidget(self.memory_page)

        # --- TAB 2: SKILLS ---
        self.skills_page = QWidget()
        skills_layout = QVBoxLayout(self.skills_page)
        skills_layout.setContentsMargins(20, 20, 20, 20)
        
        skills_title = QLabel("Loaded Agent Skills")
        skills_title.setStyleSheet("color: white; font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        skills_layout.addWidget(skills_title)
        
        self.skills_list = QListWidget()
        self.skills_list.setStyleSheet("""
            QListWidget {
                background: #25252d;
                border: 1px solid #33333d;
                border-radius: 8px;
                color: #d0d0d0;
                font-size: 14px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #33333d;
            }
        """)
        skills = ["autonomous_sales", "calendar_agent", "discord_agent", "github_agent", "gmail_agent", "notion_agent", "spotify_agent", "weather_news"]
        for s in skills:
            self.skills_list.addItem(f"✅ {s}")
            
        skills_layout.addWidget(self.skills_list)
        self.stacked_widget.addWidget(self.skills_page)

        # --- TAB 3: WHATSAPP ---
        self.whatsapp_page = QWidget()
        wa_layout = QVBoxLayout(self.whatsapp_page)
        wa_layout.setContentsMargins(20, 20, 20, 20)
        wa_layout.setSpacing(15)

        wa_title = QLabel("Live WhatsApp Feed")
        wa_title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        wa_layout.addWidget(wa_title)

        self.wa_scroll = QScrollArea()
        self.wa_scroll.setWidgetResizable(True)
        self.wa_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #555; border-radius: 4px; }
        """)

        self.wa_container = QWidget()
        self.wa_container.setStyleSheet("background: transparent;")
        self.wa_inner_layout = QVBoxLayout(self.wa_container)
        self.wa_inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.wa_inner_layout.setSpacing(15)
        
        self.wa_empty = QLabel("No new WhatsApp messages.")
        self.wa_empty.setStyleSheet("color: #777; font-size: 14px; font-style: italic;")
        self.wa_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wa_inner_layout.addWidget(self.wa_empty)

        self.wa_scroll.setWidget(self.wa_container)
        wa_layout.addWidget(self.wa_scroll)

        self.stacked_widget.addWidget(self.whatsapp_page)

        # --- TAB 4: KERNEL STREAM ---
        self.kernel_page = QWidget()
        kernel_layout = QVBoxLayout(self.kernel_page)
        kernel_layout.setContentsMargins(20, 20, 20, 20)
        kernel_layout.setSpacing(15)

        kernel_title = QLabel("Mizune Kernel Event Stream")
        kernel_title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        kernel_layout.addWidget(kernel_title)

        self.kernel_list = QListWidget()
        self.kernel_list.setStyleSheet("""
            QListWidget {
                background: #0a0a0f;
                border: 1px solid #33333d;
                border-radius: 8px;
                color: #d0d0d0;
                font-family: 'Fira Code', monospace;
                font-size: 13px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #1e1e24;
            }
        """)
        kernel_layout.addWidget(self.kernel_list)
        self.stacked_widget.addWidget(self.kernel_page)

        self.main_layout.addWidget(self.stacked_widget)

    def setupBridge(self):
        self.bridge.status_signal.connect(self.update_status)
        self.bridge.speak_signal.connect(self.add_ai_message)
        if hasattr(self.bridge, 'emotion_signal'):
            self.bridge.emotion_signal.connect(self.update_emotion)
        if hasattr(self.bridge, 'refresh_graph_signal'):
            self.bridge.refresh_graph_signal.connect(self.refresh_memory_graph)
        if hasattr(self.bridge, 'whatsapp_signal'):
            self.bridge.whatsapp_signal.connect(self.add_whatsapp_alert)
        if hasattr(self.bridge, 'kernel_signal'):
            self.bridge.kernel_signal.connect(self.add_kernel_event)
        if hasattr(self.bridge, 'memory_signal'):
            self.bridge.memory_signal.connect(self.update_memory_state)

    def add_whatsapp_alert(self, data_str):
        # Remove empty state label
        if self.wa_empty.isVisible():
            self.wa_empty.hide()
            
        try:
            data = json.loads(data_str)
            sender = data.get("sender", "Unknown")
            msg = data.get("message", "")
            urgency = data.get("urgency", "NORMAL")
            
            card = QFrame()
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            
            border_color = "#a777e3"
            bg_color = "#2b2b36"
            if urgency == "CRITICAL":
                border_color = "#ef4444"
                bg_color = "rgba(239, 68, 68, 0.1)"
            elif urgency == "HIGH":
                border_color = "#f59e0b"
                
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-left: 4px solid {border_color};
                    border-radius: 6px;
                    padding: 12px;
                }}
            """)
            
            card_layout = QVBoxLayout(card)
            
            header_layout = QHBoxLayout()
            sender_lbl = QLabel(sender)
            sender_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 14px; border: none; background: transparent;")
            
            time_lbl = QLabel(datetime.now().strftime("%I:%M %p"))
            time_lbl.setStyleSheet("color: #aaa; font-size: 11px; border: none; background: transparent;")
            
            header_layout.addWidget(sender_lbl)
            header_layout.addStretch()
            header_layout.addWidget(time_lbl)
            
            msg_lbl = QLabel(msg)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet("color: #d0d0d0; font-size: 14px; border: none; background: transparent; margin-top: 5px;")
            
            card_layout.addLayout(header_layout)
            card_layout.addWidget(msg_lbl)
            
            # Insert at top
            self.wa_inner_layout.insertWidget(0, card)
            
        except Exception as e:
            print(f"Error parsing WA alert: {e}")

    def update_emotion(self, emotion_name):
        self.emotion_label.setText(f"Emotion: {emotion_name.capitalize()}")
        
        # Color and intensity mapping
        emotion_map = {
            "neutral": (50, "#a777e3", "#d4a5ff"),      # Purple
            "happy": (80, "#4cd137", "#8cff7a"),        # Green
            "excited": (100, "#ffcc00", "#ffea75"),     # Yellow
            "sad": (20, "#00a8ff", "#7cd8ff"),          # Blue
            "angry": (90, "#e84118", "#ff795e"),        # Red
            "surprised": (85, "#ff9f43", "#ffc88f"),    # Orange
            "worried": (30, "#7f8fa6", "#b0c1d6"),      # Grey
        }
        
        val, color1, color2 = emotion_map.get(emotion_name.lower(), (50, "#a777e3", "#d4a5ff"))
        self.emotion_bar.setValue(val)
        self.emotion_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #2b2b36;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color1}, stop:1 {color2});
                border-radius: 4px;
            }}
        """)

    def add_kernel_event(self, event_json):
        try:
            event = json.loads(event_json)
            etype = event.get('event_type', 'UNKNOWN')
            proc = event.get('process_name', 'unknown.exe')
            imp = event.get('importance', 0.0)
            
            time_str = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{time_str}] [{etype}] {proc} (Imp: {imp:.2f})"
            
            # Format high importance events
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(log_line)
            if imp > 0.6:
                item.setForeground(Qt.GlobalColor.cyan)
            
            self.kernel_list.insertItem(0, item)
            
            # Keep list to max 100 items
            if self.kernel_list.count() > 100:
                self.kernel_list.takeItem(self.kernel_list.count() - 1)
        except Exception as e:
            pass

    def update_memory_state(self, state_json):
        pass

    def refresh_memory_graph(self):
        if WEB_ENGINE_AVAILABLE and hasattr(self, 'web_view'):
            self.web_view.reload()

    def update_status(self, text, color):
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        if hasattr(self, 'slime_view'):
            if text in ["Thinking...", "Processing..."]:
                self.slime_view.page().runJavaScript("setState('thinking');")
            elif text == "Listening...":
                self.slime_view.page().runJavaScript("setState('listening');")
            elif "Speaking" in text or "Responding" in text:
                self.slime_view.page().runJavaScript("setState('speaking');")
            else:
                self.slime_view.page().runJavaScript("setState('idle');")

    def add_message(self, text, is_user=False):
        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        msg_label.setFont(QFont("Segoe UI", 12))
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        if is_user:
            msg_label.setStyleSheet("color: #c0c0c0; margin-top: 15px; text-align: right; background: transparent; border: none;")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            msg_label.setStyleSheet("""
                QLabel {
                    color: #ffffff; 
                    margin-top: 10px; 
                    background-color: #333344; 
                    padding: 12px; 
                    border-radius: 8px;
                    border-left: 4px solid #a777e3;
                }
                QLabel:hover {
                    background-color: #3a3a4d;
                    border-left: 6px solid #b787f3;
                }
            """)
            
        self.chat_inner_layout.addWidget(msg_label)
        
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def add_ai_message(self, text):
        self.add_message(text, is_user=False)

    def send_message(self):
        text = self.input_field.text()
        if text.strip():
            self.add_message(text, is_user=True)
            self.bridge.send_chat(text)
            self.input_field.clear()

    def toggle_visibility(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self.input_field.setFocus()

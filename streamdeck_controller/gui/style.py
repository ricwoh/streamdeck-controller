"""Dunkles Theme (Catppuccin-Palette)."""

BG = "#1e1e2e"
BG_ALT = "#181825"
SURFACE = "#313244"
SURFACE_HI = "#45475a"
TEXT = "#cdd6f4"
SUBTEXT = "#a6adc8"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
RED = "#f38ba8"
LAVENDER = "#cba6f7"

APP_STYLESHEET = f"""
QMainWindow, QDialog, QWidget {{ background: {BG}; color: {TEXT}; }}
QLabel {{ color: {TEXT}; background: transparent; }}
QLineEdit, QComboBox, QSpinBox {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {SURFACE_HI};
    border-radius: 4px; padding: 4px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE}; color: {TEXT}; selection-background-color: {SURFACE_HI};
}}
QPushButton {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {SURFACE_HI};
    border-radius: 4px; padding: 4px 10px;
}}
QPushButton:hover {{ background: {SURFACE_HI}; }}
QPushButton:disabled {{ color: #6c7086; }}
QGroupBox {{
    border: 1px solid {SURFACE}; border-radius: 6px;
    margin-top: 10px; color: {TEXT}; padding-top: 6px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {SUBTEXT}; }}
QTabWidget::pane {{ border: 1px solid {SURFACE}; border-radius: 4px; }}
QTabBar::tab {{
    background: {SURFACE}; color: {TEXT}; padding: 5px 12px;
    border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {SURFACE_HI}; color: {ACCENT}; }}
QListWidget {{
    background: {BG_ALT}; color: {TEXT}; border: 1px solid {SURFACE};
    border-radius: 6px; outline: none;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {SURFACE_HI}; color: {ACCENT}; }}
QListWidget::item:hover {{ background: {SURFACE}; }}
QSlider::groove:horizontal {{
    height: 4px; background: {SURFACE}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px; margin: -6px 0; border-radius: 7px; background: {ACCENT};
}}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: {BG_ALT}; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_HI}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QMenu {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {SURFACE_HI}; }}
QMenu::item:selected {{ background: {SURFACE_HI}; }}
QCheckBox {{ color: {TEXT}; }}
"""

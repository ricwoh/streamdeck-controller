"""Dunkles, modernes Theme (Catppuccin-Palette)."""

BG = "#181825"
BG_ALT = "#11111b"
CARD = "#1e1e2e"
SURFACE = "#313244"
SURFACE_HI = "#45475a"
TEXT = "#cdd6f4"
SUBTEXT = "#a6adc8"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
LAVENDER = "#cba6f7"

APP_STYLESHEET = f"""
* {{ outline: none; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ background: transparent; color: {TEXT}; font-size: 13px; }}
QMainWindow > QWidget, QDialog > QWidget {{ background: {BG}; }}

QLabel {{ color: {TEXT}; background: transparent; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {CARD}; color: {TEXT}; border: 1px solid {SURFACE};
    border-radius: 8px; padding: 6px 10px;
    selection-background-color: {ACCENT}; selection-color: {BG};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {SUBTEXT}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {CARD}; color: {TEXT}; border: 1px solid {SURFACE};
    border-radius: 8px; selection-background-color: {SURFACE_HI};
    selection-color: {ACCENT}; padding: 4px;
}}

QPushButton {{
    background: {CARD}; color: {TEXT}; border: 1px solid {SURFACE};
    border-radius: 8px; padding: 6px 14px;
}}
QPushButton:hover {{ background: {SURFACE}; border: 1px solid {SURFACE_HI}; }}
QPushButton:pressed {{ background: {SURFACE_HI}; }}
QPushButton:disabled {{ color: #6c7086; }}

QGroupBox {{
    background: {CARD}; border: 1px solid {SURFACE};
    border-radius: 10px; margin-top: 12px; padding: 8px 6px 6px 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
    color: {SUBTEXT}; font-weight: bold;
}}

QTabWidget::pane {{
    background: {CARD}; border: 1px solid {SURFACE}; border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent; color: {SUBTEXT}; padding: 6px 16px;
    border-radius: 8px; margin-right: 4px; margin-bottom: 4px;
}}
QTabBar::tab:selected {{ background: {SURFACE}; color: {ACCENT}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ background: {CARD}; color: {TEXT}; }}

QListWidget {{
    background: {CARD}; color: {TEXT}; border: 1px solid {SURFACE};
    border-radius: 10px; padding: 4px;
}}
QListWidget::item {{ padding: 7px 8px; border-radius: 6px; margin: 1px 2px; }}
QListWidget::item:selected {{ background: {SURFACE_HI}; color: {ACCENT}; }}
QListWidget::item:hover:!selected {{ background: {SURFACE}; }}

QSlider::groove:horizontal {{ height: 5px; background: {SURFACE}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 16px; margin: -6px 0; border-radius: 8px; background: {TEXT};
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; border-radius: 4px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_HI}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{
    background: {CARD}; color: {TEXT}; border: 1px solid {SURFACE};
    border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SURFACE_HI}; }}

QCheckBox {{ color: {TEXT}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {SURFACE_HI}; background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}

QToolTip {{
    background: {CARD}; color: {TEXT}; border: 1px solid {SURFACE_HI};
    border-radius: 6px; padding: 4px 8px;
}}
"""

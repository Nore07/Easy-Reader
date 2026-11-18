from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def colors(theme, background_color=""):
    if background_color:
        red, green, blue = (int(background_color[i:i+2], 16) / 255 for i in (1, 3, 5))
        luminance = sum(weight * (channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4) for weight, channel in zip((0.2126, 0.7152, 0.0722), (red, green, blue)))
        # Select the higher-contrast foreground for the picked solid background.
        light_text = (1.05 / (luminance + 0.05)) > ((luminance + 0.05) / 0.05)
        palette = colors("dark" if light_text else "light")
        palette["on_accent"] = palette["paper"]
        palette["paper"] = background_color
        palette["ink"] = "#f5f5f5" if light_text else "#171717"
        palette["muted"] = "#d8ded8" if light_text else "#2a2a2a"
        return palette
    dark = theme == "dark" or (theme == "system" and QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    if dark:
        return {"paper": "#202b28", "ink": "#e7e6dc", "muted": "#acb9ae", "side": "#18231f", "line": "#3f5047", "accent": "#b5cdb6", "button": "#33483e", "selected": "#405b4b"}
    return {"paper": "#f5f3eb" if theme != "sepia" else "#eee2c9", "ink": "#283c33", "muted": "#68796c", "side": "#e8ebdf", "line": "#d8ded0", "accent": "#315743", "button": "#dfe6d7", "selected": "#cfdeca"}


def stylesheet(palette, alpha=255):
    c = palette
    paper = c["paper"].lstrip("#")
    rgb = ",".join(str(int(paper[i:i+2], 16)) for i in (0, 2, 4))
    return f"""
    QWidget {{ color: {c['ink']}; font-family: 'Microsoft YaHei'; font-size: 13px; }}
    QMainWindow {{ background: transparent; }}
    QWidget#surface {{ background: rgba({rgb},{alpha}); border: 1px solid {c['line'] if alpha else 'transparent'}; border-radius: 9px; }}
    QWidget#sidebar {{ background: {c['side']}; border-radius: 7px; }}
    QLabel#brand {{ font-size: 22px; font-weight: 600; letter-spacing: 2px; color: {c['ink'] if 'on_accent' in c else c['accent']}; }}
    QLabel#eyebrow {{ font-size: 10px; letter-spacing: 2px; color: {c['muted']}; }}
    QLabel#bookTitle {{ font-size: 18px; font-weight: 600; }}
    QLabel#chapterTitle {{ font-size: 14px; color: {c['muted']}; }}
    QLabel#status {{ color: {c['muted']}; font-size: 11px; }}
    QPushButton {{ background: {c['button']}; border: 1px solid transparent; padding: 8px 13px; border-radius: 5px; }}
    QPushButton:hover {{ border-color: {c['accent']}; }}
    QPushButton:checked {{ background: {c['selected']}; border-color: {c['accent']}; }}
    QPushButton:disabled {{ color: {c['muted']}; background: transparent; }}
    QPushButton#primary {{ color: {c.get('on_accent', c['paper'])}; background: {c['accent']}; padding: 10px 18px; }}
    QListWidget {{ background: transparent; border: none; outline: 0; padding: 3px; }}
    QListWidget::item {{ padding: 12px 8px; border-radius: 5px; }}
    QListWidget::item:selected {{ background: {c['selected']}; color: {c['ink']}; }}
    QListWidget::item:hover {{ background: {c['button']}; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ padding: 9px 16px; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ border-bottom: 2px solid {c['accent']}; }}
    QDialog {{ background: {c['paper']}; }}
    QScrollArea#preferencesScroll {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 5px; }}
    QWidget#preferencesContent, QWidget#preferencesViewport {{ background: {c['paper']}; }}
    QComboBox QAbstractItemView {{ background: {c['paper']}; color: {c['ink']}; selection-background-color: {c['selected']}; selection-color: {c['ink']}; border: 1px solid {c['line']}; }}
    QScrollArea#preferencesScroll QScrollBar:vertical {{ background: {c['side']}; width: 10px; margin: 0; }}
    QScrollArea#preferencesScroll QScrollBar::handle:vertical {{ background: {c['muted']}; min-height: 25px; border-radius: 4px; }}
    QScrollArea#preferencesScroll QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollArea#preferencesScroll QScrollBar::add-line:vertical, QScrollArea#preferencesScroll QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollArea#preferencesScroll QScrollBar::add-page:vertical, QScrollArea#preferencesScroll QScrollBar::sub-page:vertical {{ background: transparent; }}
    QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox, QLineEdit {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 4px; padding: 6px; min-height: 22px; }}
    QCheckBox {{ padding: 5px 0; }}
    QToolTip {{ background: {c['paper']}; color: {c['ink']}; border: 1px solid {c['line']}; }}
    """

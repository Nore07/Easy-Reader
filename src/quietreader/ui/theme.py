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


def stylesheet(palette, alpha=255, borderless=False):
    c = palette
    paper = c["paper"].lstrip("#")
    rgb = ",".join(str(int(paper[i:i+2], 16)) for i in (0, 2, 4))
    surface_frame = f"border: 1px solid {c['line']}; border-radius: 9px;" if alpha and not borderless else "border: none; border-radius: 0;"
    return f"""
    QWidget {{ color: {c['ink']}; font-family: 'Microsoft YaHei'; font-size: 13px; }}
    QMainWindow {{ background: transparent; }}
    QWidget#surface {{ background: rgba({rgb},{alpha}); {surface_frame} }}
    QWidget#sidebar {{ background: {c['side']}; border-radius: 7px; }}
    QWidget#pageNavigation {{ background: {c['side']}; border-radius: 7px; }}
    QWidget#titleBar {{ background: transparent; }}
    QWidget#shelfHeading {{ background: transparent; }}
    QWidget#shelfToolbar {{ background: transparent; }}
    QLabel#brand {{ font-size: 22px; font-weight: 600; letter-spacing: 2px; color: {c['ink'] if 'on_accent' in c else c['accent']}; }}
    QLabel#eyebrow {{ font-size: 10px; letter-spacing: 2px; color: {c['muted']}; }}
    QLabel#shelfTitle {{ font-size: 24px; font-weight: 600; color: {c['ink']}; padding: 2px 0; }}
    QLabel#bookTitle {{ font-size: 18px; font-weight: 600; }}
    QLabel#chapterTitle {{ font-size: 14px; color: {c['muted']}; }}
    QLabel#status {{ color: {c['muted']}; font-size: 11px; }}
    QLabel#toolbarLabel {{ color: {c['muted']}; font-size: 12px; }}
    QPushButton {{ background: {c['button']}; border: 1px solid {c['line']}; padding: 8px 14px; min-height: 20px; border-radius: 6px; }}
    QPushButton:hover {{ background: {c['selected']}; border-color: {c['accent']}; }}
    QPushButton:pressed {{ background: {c['accent']}; color: {c.get('on_accent', c['paper'])}; }}
    QPushButton:checked {{ background: {c['selected']}; border-color: {c['accent']}; }}
    QPushButton:disabled {{ color: {c['muted']}; background: transparent; }}
    QPushButton#primary {{ color: {c.get('on_accent', c['paper'])}; background: {c['accent']}; border-color: {c['accent']}; padding: 9px 16px; }}
    QPushButton#primary:hover {{ background: {c['selected']}; color: {c['ink']}; }}
    QPushButton#quietAction {{ color: {c['muted']}; background: transparent; border-color: transparent; }}
    QPushButton#quietAction:hover {{ color: {c['ink']}; background: {c['button']}; border-color: {c['line']}; }}
    QPushButton#secondaryAction {{ color: {c['ink']}; background: {c['button']}; border-color: transparent; }}
    QPushButton#windowControl {{ color: {c['muted']}; background: transparent; border: none; padding: 0; min-height: 0; border-radius: 5px; font-size: 17px; }}
    QPushButton#windowControl:hover {{ color: {c['ink']}; background: {c['button']}; }}
    QPushButton#windowClose:hover {{ color: #ffffff; background: #c7463b; }}
    QPushButton#pageNav {{ color: {c['muted']}; background: transparent; border: 1px solid transparent; padding: 6px 16px; min-height: 20px; font-weight: 500; }}
    QPushButton#pageNav:hover {{ color: {c['ink']}; background: {c['button']}; }}
    QPushButton#pageNav:checked {{ color: {c['ink']}; background: {c['paper']}; border-color: {c['line']}; font-weight: 600; }}
    QListWidget {{ background: transparent; border: none; outline: 0; padding: 3px; }}
    QListWidget::item {{ padding: 12px 8px; border-radius: 5px; }}
    QListWidget::item:selected {{ background: {c['selected']}; color: {c['ink']}; }}
    QListWidget::item:hover {{ background: {c['button']}; }}
    QListWidget#shelfList {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 7px; }}
    QListWidget#shelfList::item {{ padding: 13px 12px; border-bottom: 1px solid {c['line']}; border-radius: 4px; }}
    QTabWidget::pane {{ border: none; top: 1px; }}
    QTabBar::tab {{ color: {c['muted']}; padding: 10px 16px; margin-right: 5px; border-bottom: 2px solid transparent; }}
    QTabBar::tab:hover {{ color: {c['ink']}; background: {c['button']}; border-top-left-radius: 5px; border-top-right-radius: 5px; }}
    QTabBar::tab:selected {{ color: {c['accent']}; border-bottom: 2px solid {c['accent']}; font-weight: 600; }}
    QDialog {{ background: {c['paper']}; }}
    QScrollArea#preferencesScroll {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 5px; }}
    QWidget#preferencesContent, QWidget#preferencesViewport {{ background: {c['paper']}; }}
    QComboBox QAbstractItemView {{ background: {c['paper']}; color: {c['ink']}; selection-background-color: {c['selected']}; selection-color: {c['ink']}; border: 1px solid {c['line']}; }}
    QScrollArea#preferencesScroll QScrollBar:vertical {{ background: {c['side']}; width: 10px; margin: 0; }}
    QScrollArea#preferencesScroll QScrollBar::handle:vertical {{ background: {c['muted']}; min-height: 25px; border-radius: 4px; }}
    QScrollArea#preferencesScroll QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollArea#preferencesScroll QScrollBar::add-line:vertical, QScrollArea#preferencesScroll QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollArea#preferencesScroll QScrollBar::add-page:vertical, QScrollArea#preferencesScroll QScrollBar::sub-page:vertical {{ background: transparent; }}
    QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox, QLineEdit {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 6px; padding: 6px 9px; min-height: 24px; }}
    QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QFontComboBox:hover, QLineEdit:hover {{ border-color: {c['muted']}; }}
    QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QFontComboBox:focus, QLineEdit:focus {{ border-color: {c['accent']}; }}
    QCheckBox {{ padding: 5px 0; }}
    QToolTip {{ background: {c['paper']}; color: {c['ink']}; border: 1px solid {c['line']}; }}
    """

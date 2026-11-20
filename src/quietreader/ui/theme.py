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
    if theme == "sepia":
        return {"paper": "#eee2c9", "ink": "#40352b", "muted": "#83745f", "side": "#e7d8ba", "line": "#d4c19a", "accent": "#805b36", "button": "#e7d6b4", "selected": "#d8c29a"}
    return {"paper": "#f5f3eb", "ink": "#283c33", "muted": "#68796c", "side": "#e8ebdf", "line": "#d8ded0", "accent": "#315743", "button": "#dfe6d7", "selected": "#cfdeca"}


def stylesheet(palette, alpha=255, borderless=False, resize_outline=False, drop_highlight=False):
    c = palette
    paper = c["paper"].lstrip("#")
    rgb = ",".join(str(int(paper[i:i+2], 16)) for i in (0, 2, 4))
    alpha_percent = alpha * 100 / 255
    if resize_outline:
        surface_frame = f"border: 1px dashed {c['accent']}; border-radius: 2px;"
    elif drop_highlight:
        surface_frame = f"border: 2px dashed {c['accent']}; border-radius: 9px;"
    else:
        surface_frame = f"border: 1px solid {c['line']}; border-radius: 9px;" if alpha and not borderless else "border: none; border-radius: 0;"
    return f"""
    QWidget {{ color: {c['ink']}; font-family: 'Microsoft YaHei'; font-size: 13px; }}
    QMainWindow {{ background: transparent; }}
    #surface {{ background: rgba({rgb},{alpha_percent:.3f}%); {surface_frame} }}
    QWidget#sidebar {{ background: {c['side']}; border-radius: 7px; }}
    QWidget#pageNavigation {{ background: {c['side']}; border-radius: 7px; }}
    QWidget#titleBar {{ background: transparent; }}
    QWidget#shelfToolbar {{ background: transparent; }}
    QLabel#brand {{ font-size: 22px; font-weight: 600; letter-spacing: 2px; color: {c['ink'] if 'on_accent' in c else c['accent']}; }}
    QLabel#eyebrow {{ font-size: 10px; letter-spacing: 2px; color: {c['muted']}; }}
    QLabel#bookTitle {{ font-size: 18px; font-weight: 600; }}
    QLabel#chapterTitle {{ font-size: 14px; color: {c['muted']}; }}
    QLabel#status {{ color: {c['muted']}; font-size: 11px; }}
    QLabel#pageStatus {{ color: {c['muted']}; font-size: 11px; padding: 0 3px; }}
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
    QPushButton#bookmarkAction {{ padding: 4px 6px; min-height: 18px; font-size: 11px; }}
    QPushButton#pageControl {{ padding: 5px 7px; min-width: 28px; min-height: 20px; }}
    QPushButton#windowControl {{ color: {c['muted']}; background: transparent; border: none; padding: 0; min-height: 0; border-radius: 5px; font-size: 17px; }}
    QPushButton#windowControl:hover {{ color: {c['ink']}; background: {c['button']}; }}
    QPushButton#windowClose:hover {{ color: #ffffff; background: #c7463b; }}
    QPushButton#sidebarToggle {{ color: {c['muted']}; background: transparent; border: none; padding: 0; min-height: 0; border-radius: 0; font-size: 8px; font-weight: 600; }}
    QPushButton#sidebarToggle:hover {{ color: {c['ink']}; background: transparent; }}
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
    QProgressBar#bookProgress {{ background: {c['button']}; border: none; border-radius: 2px; }}
    QProgressBar#bookProgress::chunk {{ background: {c['accent']}; border-radius: 2px; }}
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
    QComboBox#shelfCategoryCombo {{ background: {c['side']}; border: 1px solid {c['line']}; border-radius: 9px; padding: 7px 34px 7px 12px; min-height: 24px; }}
    QComboBox#shelfCategoryCombo:hover {{ background: {c['button']}; border-color: {c['muted']}; }}
    QComboBox#shelfCategoryCombo:focus {{ border-color: {c['accent']}; }}
    QComboBox#shelfCategoryCombo::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 30px; border: none; border-top-right-radius: 8px; border-bottom-right-radius: 8px; }}
    QComboBox#shelfCategoryCombo::drop-down:hover {{ background: {c['selected']}; }}
    QComboBox#shelfCategoryCombo::down-arrow {{ image: none; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {c['muted']}; margin-top: 2px; }}
    QComboBox#shelfCategoryCombo QAbstractItemView {{ background: {c['paper']}; color: {c['ink']}; selection-background-color: {c['selected']}; selection-color: {c['ink']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 4px; outline: 0; }}
    QCheckBox {{ padding: 5px 0; }}
    QToolTip {{ background: {c['paper']}; color: {c['ink']}; border: 1px solid {c['line']}; }}
    QMenu {{ background: {c['paper']}; color: {c['ink']}; border: 1px solid {c['line']}; padding: 5px; }}
    QMenu::item {{ color: {c['ink']}; background: transparent; padding: 7px 24px 7px 10px; border-radius: 4px; }}
    QMenu::item:selected {{ color: {c['ink']}; background: {c['selected']}; }}
    QMenu::item:disabled {{ color: {c['muted']}; }}
    QMenu::separator {{ height: 1px; background: {c['line']}; margin: 4px 8px; }}
    QScrollArea#bookInfoScroll {{ background: {c['paper']}; border: none; }}
    QWidget#bookInfoViewport, QWidget#bookInfoContent {{ background: {c['paper']}; color: {c['ink']}; }}
    QLabel#bookInfoDetails {{ color: {c['ink']}; background: transparent; }}
    QLabel#bookCoverLabel {{ color: {c['muted']}; background: transparent; }}
    QPushButton#fileNavButton {{ padding: 0; min-height: 0; font-size: 14px; }}
    QSplitter#fileDialogSplitter::handle {{ background: {c['line']}; width: 1px; margin: 4px 4px; }}
    QListWidget#fileDialogPlaces {{ background: {c['side']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 5px; outline: 0; }}
    QListWidget#fileDialogPlaces::item {{ padding: 7px 10px; border-radius: 6px; }}
    QListWidget#fileDialogPlaces::item:selected {{ background: {c['selected']}; color: {c['ink']}; }}
    QListWidget#fileDialogPlaces::item:hover {{ background: {c['button']}; }}
    QTreeView#fileDialogView {{ background: {c['paper']}; color: {c['ink']}; border: 1px solid {c['line']}; border-radius: 8px; outline: 0; padding: 0; selection-background-color: {c['selected']}; selection-color: {c['ink']}; }}
    QTreeView#fileDialogView::item {{ padding: 5px 8px; }}
    QTreeView#fileDialogView::item:selected {{ background: {c['selected']}; color: {c['ink']}; }}
    QTreeView#fileDialogView::item:hover {{ background: {c['button']}; }}
    QTreeView#fileDialogView QHeaderView::section {{ background: {c['side']}; color: {c['muted']}; border: none; border-bottom: 1px solid {c['line']}; padding: 9px 10px 6px 10px; font-weight: 600; }}
    QTreeView#fileDialogView QHeaderView::section:hover {{ color: {c['ink']}; background: {c['button']}; }}
    QComboBox#fileFilterCombo {{ background: {c['side']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 6px 32px 6px 10px; min-height: 24px; }}
    QComboBox#fileFilterCombo:hover {{ background: {c['button']}; border-color: {c['muted']}; }}
    QComboBox#fileFilterCombo:focus {{ border-color: {c['accent']}; }}
    QComboBox#fileFilterCombo::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; border-top-right-radius: 7px; border-bottom-right-radius: 7px; }}
    QComboBox#fileFilterCombo::drop-down:hover {{ background: {c['selected']}; }}
    QComboBox#fileFilterCombo::down-arrow {{ image: none; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {c['muted']}; margin-top: 2px; }}
    QComboBox#fileFilterCombo QAbstractItemView {{ background: {c['paper']}; color: {c['ink']}; selection-background-color: {c['selected']}; selection-color: {c['ink']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 4px; outline: 0; }}
    QTreeView#fileDialogView QScrollBar:vertical, QListWidget#fileDialogPlaces QScrollBar:vertical {{ background: {c['side']}; width: 10px; margin: 0; }}
    QTreeView#fileDialogView QScrollBar::handle:vertical, QListWidget#fileDialogPlaces QScrollBar::handle:vertical {{ background: {c['muted']}; min-height: 25px; border-radius: 4px; }}
    QTreeView#fileDialogView QScrollBar::handle:vertical:hover, QListWidget#fileDialogPlaces QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QTreeView#fileDialogView QScrollBar::add-line:vertical, QTreeView#fileDialogView QScrollBar::sub-line:vertical, QListWidget#fileDialogPlaces QScrollBar::add-line:vertical, QListWidget#fileDialogPlaces QScrollBar::sub-line:vertical {{ height: 0; }}
    QTreeView#fileDialogView QScrollBar::add-page:vertical, QTreeView#fileDialogView QScrollBar::sub-page:vertical, QListWidget#fileDialogPlaces QScrollBar::add-page:vertical, QListWidget#fileDialogPlaces QScrollBar::sub-page:vertical {{ background: transparent; }}
    QFrame#toastNotice {{ background: {c['selected']}; border: 1px solid {c['accent']}; border-radius: 10px; }}
    QLabel#toastLabel {{ color: {c['ink']}; background: transparent; font-size: 13px; font-weight: 500; }}
    QPushButton#toastAction {{ color: {c['accent']}; background: {c['paper']}; border: 1px solid {c['accent']}; border-radius: 6px; padding: 4px 10px; min-height: 20px; }}
    QPushButton#toastAction:hover {{ background: {c['button']}; }}
    """

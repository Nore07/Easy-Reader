"""Small explicit application catalog; book contents are never translated."""
from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

EN = {
    "启用全局显示 / 隐藏和紧急退出快捷键": "Enable global show / hide and emergency exit shortcuts",
    "显示 / 隐藏快捷键": "Show / hide shortcut", "紧急退出快捷键": "Emergency exit shortcut",
    "显示 / 隐藏：{message}": "Show / hide: {message}", "紧急退出：{message}": "Emergency exit: {message}",
    "同一按键切换隐藏和显示。启用全局快捷键后，窗口隐藏或失去焦点时也可使用。\n紧急退出直接关闭程序，不隐藏到托盘，也不等待后台导入；会尝试保存当前位置。": "The same key toggles hide and show. Enable global shortcuts to use them while hidden or unfocused.\nEmergency exit closes the process, bypassing the tray and import workers. It attempts to save your position.",
    "静读": "QuietReader", "打开": "Open", "偏好": "Preferences", "隐藏": "Hide",
    "目录 / 最近": "Library", "浮窗": "Floating", "置顶": "On top", "编码": "Encoding",
    "专注": "Focus", "退出专注": "Exit focus", "进入专注模式": "Enter focus mode", "退出专注模式": "Exit focus mode",
    "我的阅读": "MY READING", "目录": "Contents", "最近": "Recent",
    "本地阅读 · 无需联网": "Local reading · Offline",
    "一本书，一处安静": "A book. A quiet moment.", "从你的本地书籍开始": "Start with a local book",
    "← 上一页": "← Previous", "下一页 →": "Next →",
    "离线优先。打开文件即可开始阅读。": "Offline first. Open a book to begin.",
    "TXT 编码": "TXT encoding", "自动识别": "Auto detect", "按此编码重试": "Retry with encoding",
    "显示 / 隐藏": "Show / hide", "打开本地文件…": "Open local file…", "阅读偏好…": "Reading preferences…", "退出 QuietReader": "Quit QuietReader",
    "打开本地书籍": "Open a local book", "阅读文件 (*.txt *.epub);;TXT (*.txt);;EPUB (*.epub)": "Books (*.txt *.epub);;TXT (*.txt);;EPUB (*.epub)",
    "正在后台导入书籍…": "Importing book in the background…",
    "{encoding} · {count} 个章节 / 分段 · 进度自动保存{author}": "{encoding} · {count} chapters / sections · Progress saved automatically{author}",
    "{page} / {pages} 页 · 全书 {progress}": "Page {page} / {pages} · Book {progress}",
    "保存失败，请检查用户数据目录的权限和可用空间。": "Could not save. Check data directory permissions and free space.",
    "按住拖动浮窗（全透明时也可使用）": "Hold to move the floating window, including when transparent",
    "拖动浮窗": "Move floating window", "打开本地 TXT / EPUB · Ctrl+O": "Open local TXT / EPUB · Ctrl+O",
    "关闭窗口（可在偏好中设置隐藏至托盘或退出）": "Close window (configure hide to tray or quit in preferences)",
    "关闭窗口": "Close window", "TXT 乱码时，手动选择编码重新读取": "Choose an encoding to reread a garbled TXT file",
    "书籍目录": "Book contents", "最近阅读": "Recent books", "全书阅读进度": "Book progress", "阅读正文": "Book text",
    "阅读偏好 · QuietReader": "Reading preferences · QuietReader", "让阅读适合你": "Make reading your own",
    "界面语言": "Interface language", "跟随系统": "System default", "配色": "Theme", "纸白": "Paper", "暖纸": "Sepia", "夜读": "Night",
    "字体": "Font", "浮窗背景色": "Floating background", "文字颜色": "Text color", "自动文字颜色": "Automatic text color",
    "选择颜色": "Choose color", "桌面取色": "Eyedropper", "跟随主题": "Use theme", "主题色": "Theme color",
    "字号（像素）": "Font size (px)", "行距倍数": "Line height", "字距（像素）": "Letter spacing (px)",
    "段距（像素）": "Paragraph spacing (px)", "页边距（像素）": "Page padding (px)", "浮窗背景不透明度": "Floating background opacity",
    "设为 0 即全透明，文字保持不透明；仅在浮窗生效。\n取色时窗口会暂时消失，单击选择，Esc / 右键取消。\n取色结果仅保存在本机；背景变化后可重新取色。": "Set to 0 for a fully transparent floating background. Text stays opaque.\nThe windows temporarily disappear for sampling. Click to select; Esc / right-click cancels.\nThe color stays local. Sample again when your background changes.",
    "使用阅读浮窗": "Use floating window", "窗口始终置顶": "Always on top", "关闭窗口时隐藏至托盘": "Close window to system tray", "启用全局显示 / 隐藏快捷键": "Enable global show / hide shortcut",
    "全局快捷键": "Global show / hide", "下一页（正文聚焦时）": "Next page (reader focused)", "上一页（正文聚焦时）": "Previous page (reader focused)", "切换专注模式": "Toggle focus mode",
    "点击修改，然后按下一个按键或组合键。Esc 取消录入。\nEsc 固定退出专注模式；打开、偏好和复制的快捷键保留。": "Click Change, then press a key or combination. Esc cancels capture.\nEsc always exits focus. Open, preferences and copy shortcuts are reserved.",
    "专注模式仅显示正文，F10（可修改）或 Esc 退出，也可从托盘或正文右键菜单退出。": "Focus shows book text only. Exit with F10 (configurable), Esc, the tray or the reader context menu.",
    "保存偏好": "Save preferences", "取消": "Cancel", "恢复默认": "Restore defaults",
    "修改 · {key}": "Change · {key}", "录入快捷键": "Capture shortcut", "请按下一个按键或组合键\nEsc 取消": "Press a key or combination\nEsc to cancel",
    "快捷键冲突": "Shortcut conflict", "快捷键格式": "Invalid shortcut",
    "请为每个操作录入一个按键或组合键。": "Capture one key or combination for every action.", "不同操作不能使用相同的快捷键。": "Each action must have a different shortcut.",
    "Esc、Ctrl+O、Ctrl+, 和 Ctrl+C 已用于退出专注、打开、偏好和复制。": "Esc, Ctrl+O, Ctrl+, and Ctrl+C are reserved for exit focus, open, preferences and copy.",
    "这个按键不能注册为 Windows 全局快捷键，请改用其他按键。": "This key cannot be registered as a Windows global shortcut. Choose another key.",
    "选择浮窗背景色": "Choose floating background color", "选择文字颜色": "Choose text color", "复制选中文字": "Copy selected text",
    "一 段 留 给 自 己 的 时 间": "A MOMENT TO YOURSELF", "把喧闹\n留在书页之外。": "Leave the noise\nbeyond the page.", "打开一本 TXT 或 EPUB\n文件与进度，只保存在这台电脑。": "Open a TXT or EPUB book\nFiles and progress stay on this computer.",
    "单击取色 · Esc / 右键取消": "Click to pick · Esc / right-click cancels", "桌面取色：单击选择，Esc 或右键取消": "Eyedropper: click to select, Esc or right-click to cancel",
    "无法获取桌面颜色，请使用“选择颜色”手动设置。": "Could not capture the screen. Use Choose color instead.",
    "当前平台不支持 Windows 全局快捷键。": "Windows global shortcuts are unavailable on this platform.", "全局快捷键格式无效。": "Invalid global shortcut.", "全局快捷键注册失败，可能已被占用。请在设置中修改；正文翻页仍可使用。": "Could not register the global shortcut; it may be in use. Change it in preferences. Page keys still work.",
    "无法启动": "Unable to start", "无法创建用户数据目录，请检查权限或使用 --data-dir 指定目录。": "Could not create the data directory. Check permissions or use --data-dir.", "QuietReader 已在运行": "QuietReader is already running", "同一数据目录的阅读器已在运行，请从托盘显示窗口。": "A reader is already using this data directory. Show it from the system tray.",
    "导入失败，文件结构可能不受支持。请检查文件后重试。": "Import failed. The file structure may be unsupported. Check the file and retry.",
    "这本书没有可阅读的文字。": "This book contains no readable text.", "文件含有异常字符，请手动指定编码或检查文件。": "The file contains invalid characters. Choose an encoding or check the file.",
    "不支持这个编码选项。": "Unsupported encoding.", "这个文件是空的。": "This file is empty.", "所选编码无法读取这个文件，请尝试其他编码。": "This encoding cannot decode the file. Try another encoding.",
    "无法可靠识别文字编码，请选择 GB18030、UTF-16 或其他编码重试。": "Could not identify the encoding reliably. Choose GB18030, UTF-16 or another encoding.",
    "EPUB 含有不支持的外部或异常资源路径。": "The EPUB contains unsupported external or invalid resource paths.", "EPUB 含有不安全的资源路径。": "The EPUB contains unsafe resource paths.",
    "EPUB 解压后过大或资源过多，当前版本不支持。": "The expanded EPUB is too large or contains too many resources.", "EPUB 加密或压缩比例异常，无法安全读取。": "The EPUB is encrypted or has an unsafe compression ratio.", "EPUB 存在重复资源，无法可靠读取。": "The EPUB contains duplicate resources and cannot be read reliably.",
    "此 EPUB 包含加密资源（可能是 DRM 或字体混淆），当前版本不支持。": "This EPUB has encrypted resources (possibly DRM or obfuscated fonts), which are unsupported.", "这不是有效的 EPUB 文件。": "This is not a valid EPUB file.", "EPUB 的阅读顺序包含不支持的内容类型。": "The EPUB reading order contains an unsupported content type.", "EPUB 中没有可阅读的文字章节。": "The EPUB contains no readable text chapters.", "EPUB 结构损坏、内容缺失或 XML 不受支持，无法读取。": "The EPUB is damaged, incomplete or contains unsupported XML.",
    "请选择 TXT 或未加密的 EPUB 文件。": "Choose a TXT or unencrypted EPUB file.", "文件不存在或无法访问，请重新定位文件。": "The file is missing or inaccessible. Locate it again.", "文件超过 32 MiB，当前版本暂不支持。": "Files over 32 MiB are not supported yet.", "读取文件失败，请检查权限，或重新定位文件。": "Could not read the file. Check permissions or locate it again.",
    "保存数据来自不支持的版本。已保护原文件，本次不会保存更改。": "The saved data uses an unsupported version. The original is protected; changes will not be saved.", "上次保存数据损坏，已从备份恢复。": "The saved data was damaged and has been restored from backup.", "保存数据无法读取，已使用默认设置；原文件保留。": "Saved data could not be read. Defaults are in use; the original file is preserved.",
}


def resolve_language(language="system"):
    if language == "system":
        return "zh_CN" if QLocale.system().language() == QLocale.Language.Chinese else "en"
    return "en" if language == "en" else "zh_CN"


def tr(text, language="system", **values):
    result = EN.get(text, text) if resolve_language(language) == "en" else text
    return result.format(**values) if values else result


def install_qt_translator(application, language):
    code = resolve_language(language)
    if getattr(application, "_quietreader_language", None) == code:
        return
    old = getattr(application, "_quietreader_translator", None)
    if old:
        application.removeTranslator(old)
        old.deleteLater()
    translator = QTranslator(application)
    if code == "zh_CN":
        directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load("qtbase_zh_CN", directory) or translator.load("qt_zh_CN", directory):
            application.installTranslator(translator)
    application._quietreader_language = code
    application._quietreader_translator = translator

"""Small explicit application catalog; book contents are never translated."""
from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

EN = {
    "排版": "Layout",
    "EPUB 插图超过 8 MiB，无法安全读取。": "An EPUB illustration exceeds 8 MiB.",
    "EPUB 插图尺寸过大或格式不受支持。": "An EPUB illustration is oversized or unsupported.",
    "EPUB 插图损坏或格式不受支持。": "An EPUB illustration is damaged or unsupported.",
    "EPUB 插图结构不受支持。": "The EPUB illustration structure is unsupported.",
    "EPUB 插图数量超过当前支持范围。": "This EPUB exceeds the illustration count limit.",
    "EPUB SVG 插图包含不支持的活动或外部内容。": "An SVG illustration contains unsupported active or external content.",
    "阅读界面": "Reading layout",
    "调整会立即预览当前书页；保存后生效，取消恢复原设置。": "Changes preview on your current page immediately. Save to keep them, or cancel to restore.",
    "启用全局显示 / 隐藏和紧急退出快捷键": "Enable global show / hide and emergency exit shortcuts",
    "显示 / 隐藏快捷键": "Show / hide shortcut", "紧急退出快捷键": "Emergency exit shortcut",
    "显示 / 隐藏：{message}": "Show / hide: {message}", "紧急退出：{message}": "Emergency exit: {message}",
    "同一按键切换隐藏和显示。启用全局快捷键后，窗口隐藏或失去焦点时也可使用。\n紧急退出直接关闭程序，不隐藏到托盘，也不等待后台导入；会尝试保存当前位置。": "The same key toggles hide and show. Enable global shortcuts to use them while hidden or unfocused.\nEmergency exit closes the process, bypassing the tray and import workers. It attempts to save your position.",
    "静读": "QuietReader", "打开": "Open", "添加书籍": "Add books", "配置": "Configuration", "隐藏": "Hide",
    "置顶": "On top", "编码": "Encoding",
    "专注": "Focus", "退出专注": "Exit focus", "进入专注模式": "Enter focus mode", "退出专注模式": "Exit focus mode",
    "我的阅读": "MY READING", "阅读": "Reading", "书架": "Bookshelf", "阅读 / 书架": "Reading / bookshelf",
    "进入阅读页面，查看目录、书签和资料": "Go to Reading to view contents, bookmarks, and book info",
    "浏览最近阅读、所有书籍和分类": "Browse recent, all books, and categories",
    "目录": "Contents", "最近": "Recent", "最近阅读": "Recently read", "所有书籍": "All books", "分类": "Categories", "未分类": "Unclassified",
    "页码": "Pages", "位置": "Places", "书签": "Bookmarks", "资料": "Book info", "书籍分类": "Book categories", "分类中的书籍": "Books in category",
    "移动": "Move", "移除": "Remove", "移动到分类": "Move to category", "从书架移除": "Remove from bookshelf", "新建分类": "New category", "删除分类": "Delete category", "分类名称": "Category name",
    "删除分类及书籍": "Delete category and books", "仅删除分类，书籍移回未分类": "Delete category only; move books to unclassified",
    "删除分类“{name}”时，如何处理其中的书籍？": "What should happen to books in category “{name}”?",
    "确定从书架移除《{title}》吗？书架中的副本会被删除。": "Remove “{title}” from the bookshelf? Its managed copy will be deleted.",
    "已添加 {count} 本书到书架。": "Added {count} book(s) to the bookshelf.", "所选书籍已在书架中。": "The selected book(s) are already on the bookshelf.", "已创建分类“{name}”。": "Created category “{name}”.",
    "已将《{title}》移动到“{category}”。": "Moved “{title}” to “{category}”.", "已从书架移除《{title}》。": "Removed “{title}” from the bookshelf.", "已删除分类“{name}”。": "Deleted category “{name}”.",
    "书架目录不能是符号链接。": "The bookshelf folder cannot be a symbolic link.", "书架路径不是文件夹。": "The bookshelf path is not a folder.", "书架未分类目录不能是符号链接。": "The unclassified bookshelf folder cannot be a symbolic link.",
    "分类名称无效。": "Invalid category name.", "分类名称为空、重复或包含文件夹不允许的字符。": "The category name is empty, duplicated, or contains characters that folders do not allow.",
    "找不到这个书架分类。": "The bookshelf category was not found.", "这个分类已经存在。": "This category already exists.", "无法创建分类：{error}": "Could not create the category: {error}",
    "书籍文件不存在或无法访问。": "The book file is missing or inaccessible.", "请选择 TXT 或 EPUB 文件。": "Choose a TXT or EPUB file.", "书架中的书籍不能是符号链接。": "Bookshelf entries cannot be symbolic links.",
    "书架文件必须直接位于未分类或一个分类文件夹中。": "Bookshelf files must be directly inside Unclassified or one category folder.", "书架只支持 TXT 和 EPUB 文件。": "The bookshelf supports TXT and EPUB files only.",
    "复制书籍失败：{error}": "Could not copy the book: {error}", "移动书籍失败：{error}": "Could not move the book: {error}", "删除书架书籍失败：{error}": "Could not remove the bookshelf copy: {error}",
    "未分类文件夹不能删除。": "The Unclassified folder cannot be deleted.", "分类中包含子文件夹，无法安全删除或移动。": "The category contains nested folders and cannot be safely deleted or moved.",
    "分类中包含无法安全移动的内容。": "The category contains items that cannot be moved safely.", "分类中包含非书籍或无法安全处理的内容。": "The category contains non-book or unsupported items that cannot be safely handled.",
    "删除分类失败：{error}": "Could not delete the category: {error}", "分类移动失败，回滚也未完成：{error}; {rollback}": "Moving the category failed and rollback was incomplete: {error}; {rollback}", "移动分类书籍失败：{error}": "Could not move the category books: {error}",
    "添加书签": "Add bookmark", "编辑笔记": "Edit note", "删除书签": "Remove bookmark", "笔记": "Note",
    "书签名称": "Bookmark label", "书签名称：{label}": "Bookmark: {label}", "第 {page} 页": "Page {page}",
    "书签已存在。": "A bookmark already exists at this location.", "书签数量已达上限。": "The bookmark limit has been reached.",
    "书签已添加。": "Bookmark added.", "书签已删除。": "Bookmark removed.", "打开书籍以查看资料。": "Open a book to view its details.",
    "暂无书籍资料。": "No book details are available.", "没有可用封面": "No cover available",
    "书名：{value}": "Title: {value}", "作者：{value}": "Author: {value}", "语言：{value}": "Language: {value}",
    "出版者：{value}": "Publisher: {value}", "出版日期：{value}": "Published: {value}", "标识符：{value}": "Identifier: {value}", "简介：{value}": "Description: {value}",
    "本地阅读 · 无需联网": "Local reading · Offline",
    "一本书，一处安静": "A book. A quiet moment.", "从你的本地书籍开始": "Start with a local book",
    "← 上一页": "← Previous", "下一页 →": "Next →", "上一章": "Prev. chapter", "下一章": "Next chapter",
    "离线优先。添加书籍即可开始阅读。": "Offline first. Add a book to begin.",
    "TXT 编码": "TXT encoding", "自动识别": "Auto detect", "按此编码重试": "Retry with encoding",
    "显示 / 隐藏": "Show / hide", "添加书籍…": "Add books…", "配置…": "Configuration…", "退出 QuietReader": "Quit QuietReader",
    "添加本地书籍": "Add local books", "阅读文件 (*.txt *.epub);;TXT (*.txt);;EPUB (*.epub)": "Books (*.txt *.epub);;TXT (*.txt);;EPUB (*.epub)",
    "正在后台导入书籍…": "Importing book in the background…",
    "{encoding} · {count} 个章节 / 分段 · 进度自动保存{author}": "{encoding} · {count} chapters / sections · Progress saved automatically{author}",
    "{page} / {pages} 页 · 全书 {progress}": "Page {page} / {pages} · Book {progress}",
    "书内链接目标不可用。": "This link points to a location that is unavailable in the reading order.",
    "保存失败，请检查用户数据目录的权限和可用空间。": "Could not save. Check data directory permissions and free space.",
    "切换阅读与书架页面": "Switch between reading and bookshelf",
    "添加本地 TXT / EPUB 到书架 · Ctrl+O": "Add local TXT / EPUB to bookshelf · Ctrl+O",
    "TXT 乱码时，手动选择编码重新读取": "Choose an encoding to reread a garbled TXT file",
    "书籍目录": "Book contents", "全书阅读进度": "Book progress", "阅读正文": "Book text",
    "阅读配置 · QuietReader": "Configuration · QuietReader", "让阅读适合你": "Make reading your own",
    "界面语言": "Interface language", "跟随系统": "System default", "配色": "Theme", "纸白": "Paper", "暖纸": "Sepia", "夜读": "Night",
    "字体": "Font", "专注模式背景色": "Focus mode background", "文字颜色": "Text color", "自动文字颜色": "Automatic text color",
    "选择颜色": "Choose color", "桌面取色": "Eyedropper", "跟随主题": "Use theme", "主题色": "Theme color",
    "字号（像素）": "Font size (px)", "行距倍数": "Line height", "字距（像素）": "Letter spacing (px)",
    "段距（像素）": "Paragraph spacing (px)", "页边距（像素）": "Page padding (px)", "专注模式背景不透明度": "Focus mode background opacity",
    "设为 0 即全透明，文字保持不透明；背景色、透明度和桌面取色仅在专注模式生效。\n取色时窗口会暂时消失，单击选择，Esc / 右键取消。\n取色结果仅保存在本机；背景变化后可重新取色。": "Set to 0 for a fully transparent background while keeping text opaque. Background color, opacity and desktop sampling apply only in Focus mode.\nThe window temporarily disappears for sampling. Click to select; Esc or right-click cancels.\nThe color stays local. Sample again when your desktop changes.",
    "窗口始终置顶": "Always on top", "关闭窗口时隐藏至托盘": "Close window to system tray", "启用全局显示 / 隐藏快捷键": "Enable global show / hide shortcut",
    "全局快捷键": "Global show / hide", "下一页（正文聚焦时）": "Next page (reader focused)", "上一页（正文聚焦时）": "Previous page (reader focused)",
    "下一章（正文聚焦时）": "Next chapter (reader focused)", "上一章（正文聚焦时）": "Previous chapter (reader focused)", "切换专注模式": "Toggle focus mode",
    "PageUp / PageDown 翻页，Ctrl+PageUp / Ctrl+PageDown 切换章节；两组按键都可以修改。": "Use PageUp / PageDown for pages and Ctrl+PageUp / Ctrl+PageDown for chapters. Both shortcuts are configurable.",
    "点击修改，然后按下一个按键或组合键。Esc 取消录入。\nEsc 固定退出专注模式；添加书籍、配置和复制的快捷键保留。": "Click Change, then press a key or combination. Esc cancels capture.\nEsc always exits Focus mode. Add books, configuration and copy shortcuts are reserved.",
    "专注模式仅显示正文，F10（可修改）或 Esc 退出，也可从托盘或正文右键菜单退出。": "Focus shows book text only. Exit with F10 (configurable), Esc, the tray or the reader context menu.",
    "保存配置": "Save configuration", "取消": "Cancel", "恢复默认": "Restore defaults",
    "修改 · {key}": "Change · {key}", "录入快捷键": "Capture shortcut", "请按下一个按键或组合键\nEsc 取消": "Press a key or combination\nEsc to cancel",
    "快捷键冲突": "Shortcut conflict", "快捷键格式": "Invalid shortcut",
    "请为每个操作录入一个按键或组合键。": "Capture one key or combination for every action.", "不同操作不能使用相同的快捷键。": "Each action must have a different shortcut.",
    "Esc、Ctrl+O、Ctrl+, 和 Ctrl+C 已用于退出专注、添加书籍、配置和复制。": "Esc, Ctrl+O, Ctrl+, and Ctrl+C are reserved for exit Focus mode, add books, configuration and copy.",
    "这个按键不能注册为 Windows 全局快捷键，请改用其他按键。": "This key cannot be registered as a Windows global shortcut. Choose another key.",
    "选择专注模式背景色": "Choose Focus mode background color", "选择文字颜色": "Choose text color", "复制选中文字": "Copy selected text",
    "一 段 留 给 自 己 的 时 间": "A MOMENT TO YOURSELF", "把喧闹\n留在书页之外。": "Leave the noise\nbeyond the page.", "添加一本 TXT 或 EPUB\n文件与进度，只保存在这台电脑。": "Add a TXT or EPUB book\nFiles and progress stay on this computer.",
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

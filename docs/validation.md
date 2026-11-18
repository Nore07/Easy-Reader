# 首版本地阅读器验收记录

日期：2026-11-17。环境：Windows 11 build 22631 x64，仓库 `.venv` 的 CPython 3.12.10，PySide6 Essentials 6.12.0。

## 已执行

- `.\.venv\Scripts\python.exe -m pytest -q`：24 项通过。覆盖编码与手动选择、TXT 标题/长文分块、EPUB 元数据/导航/命名空间、加密和不安全压缩包拒绝、空文件/缺失文件、设置限制、语义位置、原子保存/坏状态恢复/未来版本保护、屏幕移除回退、实际 Qt 分页/Unicode 代理对/选择复制/字号重排/重启恢复/热键冲突持续提示。
- `.\.venv\Scripts\python.exe scripts/gui_smoke.py`：实际 `windows` Qt 平台通过；导入、翻页、设置窗口打开、夜间浮窗、缩放语义位置、托盘隐藏/显示、全局热键注册、Windows 原生 WM_HOTKEY 事件分发及重开恢复。截图检查修复了默认目录隐藏和编码设置占用空间的问题。
- `.\.venv\Scripts\python.exe -m pip check`：没有依赖冲突。
- `scripts/build.ps1`：已构建过 Windows onedir 应用；最终打包后独立可执行文件的结果见本记录末尾。
- 9,300,018 字节的本地生成 TXT：解析 1.649 秒、132 个分段、最大分段 23,982 字符。仅为本机一次样本，不代表所有文件性能或 UI 内存基线。
- 代码检查：书籍 HTML 从未送入浏览器或 Qt 富文本视图，EPUB 转为纯文本；元数据标签固定 PlainText；应用没有网络请求或遥测代码。`urllib.parse` 仅做 ZIP 内部路径验证。

GUI 测试仅使用脚本原创的临时文本及构造的 EPUB，不读取用户书籍，测试数据目录和窗口会清理。截图/JSON 报告保留在忽略的 `artifacts/`，构建产物在忽略的 `dist/`。

## 未覆盖与限制

- Windows 10、其他硬件、无 Python 的干净系统、100%/125%/150% DPI、多显示器真实拔插、不同桌面背景下透明度可读性，仍需实机验收。坐标恢复目前仅有算法测试。
- 当前 Qt 6.12 [官方平台表](https://doc.qt.io/qt-6/supported-platforms.html)列出 Windows 10 1809+，并声明其为最后支持 Windows 10 的版本，因此依赖范围限制为 `<6.13`；这不是本应用已通过 Windows 10 验收的证据。
- 热键分发测试发送到本进程消息队列，未模拟用户物理键盘或验证所有其他程序的热键冲突行为。
- EPUB 样本为构造样本；尚未完成多出版社真实合法样本集回归。图片、封面、复杂样式、竖排、单 XHTML 内多个目录锚点不支持。
- 未实现书签、全文搜索、OCR、安装器、自动更新、数字签名或任何在线来源。没有声称覆盖原规格的全部后续阶段。
- 完整许可通知和正式分发条件见 `third-party.md`；当前构建用于本机测试。

## 最终构建结果

`scripts/packaged_smoke.py` 已通过：独立 EXE 启动、导入本地书籍、保存语义位置并以退出码 0 关闭。启动加导入的本次观测为 2.203 秒。最终完整回归仍为 24 项通过。

打包期间发现环境 PATH 内其他工具的 ICU 同名 DLL 被 PyInstaller 收集，造成 QtCore 加载失败。已通过构建期间限制 PATH、清理打包缓存解决；最终依赖分析中不再包含该外部工具的 ICU。该限制仅作用于脚本运行期间，finally 恢复原 PATH，不修改系统环境配置。

## 透明背景与桌面取色增量

新增透明背景、颜色配置持久化和输入限制、DPI/负坐标采样、取色选择/取消/失败恢复的回归测试。`scripts/background_smoke.py` 在真实 Windows 上以应用自建的纯色窗口验证桌面采样，经过模态偏好窗口选择/取消，并检查顶层合成的阅读区像素 alpha 为 0、窗口整体 opacity 为 1。截图仅保存阅读器自身的渲染，不保存桌面取色截图。

本增量最终结果：30 项测试通过，原有 GUI 冒烟和新增背景冒烟均通过，Windows 包重新构建成功。`packaged_smoke.py` 的普通启动及 `--transparent` 启动均通过，后者还核验了透明度 0 和自定义颜色的保存与恢复。

多屏混合 DPI 的坐标换算有构造样本测试，实际多屏、受保护画面以及远程桌面取色仍需人工确认；取色失败可改用手动颜色选择。取色不会持续监测桌面，完全透明背景下的对比度依赖用户选择与实际背景匹配的配色。

## 文字颜色、语言、专注与按键录入增量

37 项 pytest 通过。新增实际文字像素颜色、中英文切换不改变书籍内容及语义锚点、按键捕获/取消、组合键翻页、专注切换及退出恢复、无其他可见控件、专注不跨重启开启、原浮窗样式和目录恢复、Windows 虚拟键映射与配置保存测试。

真实 Windows 的 `scripts/focus_smoke.py` 已通过：点击修改并录入 Ctrl+J，中文/英文即时切换，自定义字色，点击进入仅正文的透明页面，通过组合键翻页、Esc 退出、修改后的 F8 再次切换及托盘退出，最后重启恢复字色/语言/映射和进度。英文设置、键位区、紧凑英文窗口及纯文字专注截图已检查。原有 GUI 与背景取色冒烟通过。

仍未覆盖所有键盘布局、系统保留快捷键、Windows 10 及真实多屏 DPI；不能假定所有硬件上的 Fn / 系统组合都会向应用发送按键事件。

最终 Windows 包输出到 `dist/focus-release/QuietReader/QuietReader.exe`；独立 EXE 的 `--focus` 场景通过英文配置保存、F8 原生键盘进入无标题栏专注、J 翻页、Esc 恢复和正常退出，`--transparent` 场景也通过。构建时原目录中的旧版正在运行，覆盖构建因占用失败；已在独立目录成功重建，并只补回旧目录缺失的 6 个运行文件，没有覆盖占用文件或关闭用户程序。构建脚本现会检查目标程序占用并选择独立输出，最新成功路径写入忽略的 `artifacts/latest-build.txt`。

## 2026-11-18：显隐与紧急退出快捷键

43 项测试通过。新增紧急键保存、旧绑定兼容、全局虚拟键冲突、不同注册 ID 只触发对应动作、无托盘时显隐键、本地紧急退出、保存失败仍退出、不等待导入线程池、偏好按键录入及录入期间暂停/恢复全局键的验证。

最终包为 `dist/shortcuts-release/QuietReader/QuietReader.exe`。`packaged_smoke.py --emergency` 通过全局显隐消息分发、隐藏后退出、实例锁释放和重启恢复，测试中“关闭到托盘”开启，进程仍按预期退出，观测退出耗时 0.172 秒。测试只作用于临时数据目录中的测试进程；未关闭用户正在使用的程序。`--focus` 和 `--transparent` 独立 EXE 回归也通过。

全局测试向目标进程 GUI 线程发送 WM_HOTKEY 消息，验证实际注册和分发，不等同于覆盖全部物理键盘布局。紧急退出尝试进行一次原子保存；磁盘异常时仍退出，因此不能承诺所有故障下保留最后一次位置。

## 2026-11-18：夜读偏好及滚轮误改修复

根据用户截图复现：偏好的滚动内容区仍是系统浅色背景，文字继承夜读浅色，且滚轮直接改变输入控件值。新增测试先观察到这两个失败，再修复偏好独立主题及滚轮事件路由。

49 项测试通过。覆盖深色、浅色、暖纸偏好背景及文字，不受阅读浮窗透明度、桌面取色和正文自定义颜色影响；配色即时预览不修改父窗口设置。控件聚焦/未聚焦两种状态下，所有数值框、字体/语言/配色下拉框及其行编辑器均不响应滚轮改值，滚动事件转交页面，显式键盘编辑仍有效。

`scripts/preferences_smoke.py` 已在真实 Windows 验证中英文夜读、浅色预览、滚轮只滚动及键盘编辑，并检查生成的界面截图。滚动到末尾时继续向下不改变页面或控件值，符合预期。最终包及独立程序回归结果随本阶段交付提供。

最终包为 `dist/preferences-release/QuietReader/QuietReader.exe`。独立 EXE 的 `--focus`、`--emergency` 和 `--transparent` 回归全部通过；旧程序和已有阅读状态未被修改。

## 2026-11-18：实时排版与 EPUB 插图

字体及五项排版数值统一到独立非模态“阅读界面”面板，当前书页实时预览，保存持久化、取消恢复。图片通过本地 ZIP 资源与单字符锚点接入 Qt 文档，不执行原书 HTML；按页尺寸等比缩放，保留图文顺序并去除图片段距生成的尾部空页。SVG 在解码前检查外部引用与活动内容，资源字节、像素和引用数量设上限。

54 项测试通过：包含实际图片上下部像素、图文顺序、图片型 SVG 章节、无效及外部资源拒绝、面板即时预览/取消/保存及全部原功能。Windows `scripts/illustrations_smoke.py` 验证图像像素和真实阅读面板，书页及面板截图已检查。样本为自行生成的 PNG、SVG 和 EPUB，未使用用户书籍；真实出版物的复杂 CSS、SVGZ、SVG 内嵌图像等仍有限制，见 README。

最终包：`dist/illustrated-release/QuietReader/QuietReader.exe`。独立 EXE 的 `--illustrated` 已实际导入含 PNG 和 SVG 的 EPUB，保存位置并正常退出；`--focus` 与 `--emergency` 回归通过。原偏好与专注的 Windows 冒烟也通过。排版预览面板不等待关闭即可在阅读器观察变化；设置仍使用版本 1，原偏好的排版字段迁移到专门入口，原数值保留。

## 2026-11-18：专注模式移除窗口边框

专注时除 Qt 阅读区域外，还关闭 Windows 11 DWM 绘制的原生窗口边框；退出专注恢复系统默认边框。透明阅读区域同时不再保留 CSS 边框或圆角。DWM 边框颜色属性从 Windows 11 build 22000 起支持，其他平台或不支持该属性的版本会安全忽略原生设置。

57 项 pytest 通过，覆盖进入/退出时边框属性调用、DWM 隐藏/默认颜色参数及全透明表面无边框样式。Windows 11 的临时 Qt 窗口确认 DWM 隐藏边框调用成功；`scripts/focus_smoke.py` 通过。新打包 EXE 的 `--focus` 和 `--transparent` 冒烟通过。

新包为 `dist/focus-border-release/QuietReader/QuietReader.exe`。DWM API 依据 [DWMWINDOWATTRIBUTE 官方文档](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute)；Windows 10 实机未验证。

## 2026-11-18：EPUB 章节和书内导航

新增 EPUB 3 层级目录、EPUB 2 NCX 目录、可选印刷页码列表、pagebreak 页码回退、landmarks 结构位置、正文片段链接、独立上一章/下一章按钮与可修改章节快捷键。分段长章节仍可逐页连续阅读；章节跳转按原 EPUB 文档分组。所有跳转只解析 EPUB ZIP 内的路径与锚点，不访问外网。目录和页码导航基于 EPUB 3.3 的 spine、nav toc、可选 page-list 和 landmarks 结构（[EPUB 3.3](https://www.w3.org/TR/epub-33/)；[EPUB Reading Systems 3.3](https://www.w3.org/TR/epub-rs-33/)）。

63 项 pytest 通过。`scripts/navigation_smoke.py` 在真实 Windows Qt 窗口验证层级目录、书内链接、页码/landmark 跳转、章节按钮和自定义按键；`scripts/packaged_smoke.py --navigation` 验证打包 EXE 导入临时导航 EPUB、保存阅读位置并正常退出。打包目录为 `dist/epub-navigation-release/QuietReader/QuietReader.exe`。冒烟脚本首次运行发现测试夹具导入路径缺少 `src`，已修复后重新通过。

当前覆盖重排版 EPUB 的常见导航与跳转，不代表支持 EPUB 全部规范。固定版式、DRM、脚本、音视频、外部资源、任意 CSS 和复杂 MathML 仍不支持；EPUB 2/3 测试使用本地构造样本，真实出版物回归尚未覆盖。

## 2026-11-18：书架与分类管理

书目侧栏拆为“阅读”和“书架”：目录、书签、页码与位置留在阅读模块；书架提供最近阅读、全部书籍和分类。添加入口支持多选并将副本放入用户数据目录的 `书架/未分类/`，原文件保留。新建分类后可以将书架副本移动到 `书架/<分类>/`；删除分类时明确提供删除书籍或移回未分类两种选项，取消为默认动作。旧版外部路径书目仍显示，首次加入或移动时复制进书架，位置、书签和最后阅读 ID 会随路径更新。

`.venv` 下 `pytest -q`：95 项通过。`scripts/shelf_smoke.py` 在实际 Qt 窗口验证添加、副本保存、分类移动、两种分类删除和阅读位置/书签迁移。独立 Windows 包普通场景和 `--illustrated` 均通过，确认 TXT/含 PNG、SVG 的 EPUB 都复制后可读、源文件保留、进度保存并正常退出。所有冒烟只使用临时目录和自建书籍；未读取用户书籍。分类删除会拒绝处理目录中嵌套文件夹、非书籍文件或符号链接。

## 2026-11-18：书签、书籍资料和封面

状态文件兼容地新增本地书签与纯文本笔记：上限 200 条、每条笔记最多 1000 个字符；已有版本 1 状态文件没有书签字段时自动视为空集合。书签可以恢复章节/字符偏移，也能编辑和删除笔记。EPUB 3 `cover-image` 与 EPUB 2 `meta name="cover"` 读取封面；缺失、无效或不可解码的封面回退到资料文字。资料面板显示书名、作者、语言、标识符、出版者、日期和简介，全部按纯文本呈现。

71 项 pytest 通过，覆盖两种 EPUB 封面元数据、缺失/损坏封面、旧状态读取、非法记录过滤、笔记限长、UI 双语显示、书签新增/删除和重启定位。`scripts/epub_library_smoke.py` 在真实 Windows Qt 窗口验证封面和书签流程；新打包 EXE 通过 `scripts/packaged_smoke.py --library` 导入元数据及独立封面的临时 EPUB、保存位置并正常退出。包位于 `dist/epub-library-release/QuietReader/QuietReader.exe`。

封面只显示 EPUB 声明的本地图片资源，不保存到用户状态文件；元数据简介从 XML 中提取为纯文本，不执行书中标记或样式。回归样本为本地构造的 EPUB，尚未覆盖不同出版软件生成的真实书籍集合。

## 2026-11-18：EPUB 基础语义排版

在纯文本抽取中为标题层级、粗体、斜体、删除线、下划线、高亮、引用、编号/项目符号列表、行内代码、上标/下标和水平分隔线保留受限格式范围，每个正文文档最多 50,000 个标记。格式范围在空白归一化与长章节分块时同步换算；阅读器只向 Qt 文档插入已提取的文本、格式枚举和本地插图，不把原始 XHTML/CSS/脚本交给渲染层。版面使用用户的字体设置，标题字号按层级实时缩放，链接颜色和可点击行为保持优先级。

75 项 pytest 通过，覆盖上述格式、标题内嵌强调、实体/活动内容过滤、长章节跨分块格式范围、Qt 字符与段落格式、普通 TXT 默认样式及已有功能。`scripts/epub_formatting_smoke.py` 在真实 Windows 窗口检查排版并生成分页截图；`scripts/navigation_smoke.py`、`scripts/illustrations_smoke.py` 和 `scripts/epub_library_smoke.py` 同轮通过。最终独立包 `dist/epub-complete-release/QuietReader/QuietReader.exe` 的 `--formatted`、`--navigation`、`--library` 和 `--illustrated` 冒烟均通过，支持启动、导入、保存位置与干净退出。

这是面向重排版阅读的基础语义子集，不应用原书 CSS 样式表，也不等同浏览器排版。固定版式、竖排、任意 CSS、复杂 MathML、嵌入脚本、媒体覆盖和在线资源仍不支持。验证使用自制 EPUB 样本；真实出版物兼容性仍需后续用用户挑选的书籍样本复核。

## 2026-11-18：阅读导航、书架页面与专注模式整合

阅读页签现在按目录、书签、资料、页码、位置排列；资料仅在打开书籍后显示。书架改为右侧主页面，由“阅读 / 书架”按钮切换。配置按钮和配置窗口统一使用“配置 / Configuration”；独立浮窗设置已移除，旧 `floating` 字段会被忽略。专注模式沿用背景色、桌面取色、0–100% 背景透明度与置顶设置，只留下书中文字。

Qt 回归为 95 项通过。Windows 原生冒烟通过 `gui_smoke.py`、`focus_smoke.py`、`background_smoke.py`、`preferences_smoke.py`、`navigation_smoke.py` 和 `epub_library_smoke.py`。背景冒烟在全屏纯色底窗上比较专注窗口显示前后的桌面合成像素，避免仅凭控件截图误判透明效果。Windows onedir 包 `dist/reading-config-focus-final/QuietReader/QuietReader.exe` 构建成功；`packaged_smoke.py --transparent` 与 `--focus` 均通过。

Qt 官方文档说明，`WA_TranslucentBackground` 在窗口显示后切换并非所有平台都可靠，因此该属性改为在创建原生窗口前初始化，普通模式使用不透明背景配色。现有 Windows 11 实机桌面合成已验证专注背景透明，且键盘退出后普通窗口恢复。

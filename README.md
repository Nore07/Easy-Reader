# QuietReader · 静读

Windows 本地 TXT / EPUB 阅读器。使用 **Python + PySide6（Qt Widgets）**，文件和进度保存在本机，无网络抓取、在线书源、遥测或上传。

本次实施根据用户确认调整了原开发规格：首版仅本地阅读，不接入 AnyReader，不使用 Electron。详见 [技术决策](docs/decisions/0001-python-local-reader.md)。

## 使用已有虚拟环境

在仓库根目录的 PowerShell 执行；无需激活环境，不使用全局 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe run.py
# 也可直接打开一本书
.\.venv\Scripts\python.exe run.py "D:\Books\一本书.epub"
```

可选：`.\.venv\Scripts\python.exe -m pip install -e . --no-build-isolation` 后使用 `.\.venv\Scripts\python.exe -m quietreader`。当前开发环境为 Windows / CPython 3.12.10。精确运行依赖在 `requirements-lock.txt`，版本范围在 `requirements.txt` / `pyproject.toml`。

## 阅读操作

- **打开**或 `Ctrl+O`：选择 TXT / EPUB。最近阅读和目录在左侧，可单击或键盘选择后回车跳转。
- 正文获得焦点时，`PageDown` / `PageUp` 翻页；页尾自动进入下一章节。底部滑块跳转全书进度。可选中文字后 `Ctrl+C` 或右键复制。
- **偏好**或 `Ctrl+,`：设置字体、字号、行距、字距、段距、页边距、配色和快捷键；更改排版仍保持语义阅读位置。
- **文字颜色**：偏好 → 文字颜色 → 选择颜色，只改变书籍正文；选择“自动文字颜色”恢复主题/背景的自动配色。
- **界面语言**：偏好 → 界面语言，可选“跟随系统 / 简体中文 / English”；保存后主界面、菜单和提示切换语言，书籍内容保持原文。英文界面针对较长标签换行，紧凑窗口收起品牌和侧栏。
- **偏好窗口操作**：偏好使用独立、不透明的主题配色，夜读模式下滚动内容区和下拉列表也采用深色；切换配色可即时预览，取消不会更改阅读器设置。滚轮经过数值框、字体、语言或配色下拉框时只滚动页面，不改动选项，即使控件已获得焦点；修改请使用输入、方向键、加减按钮或打开下拉列表选择。
- **专注模式**：打开书后点击“专注”或按默认 `F10`，页面只保留正文，强制透明、无边框，隐藏全部按钮、书名、目录、进度、状态及缩放手柄。再按专注快捷键或 `Esc` 退出；也可通过托盘中的“退出专注模式”或正文右键菜单退出。页面内不留退出按钮。退出恢复原窗口外观和语义位置，重启默认恢复带操作界面的阅读器。
- **浮窗**：隐藏系统边框和侧栏，保留拖动顶栏、右下角缩放和边缘缩放；背景不透明度 0%–100%，在偏好中设为 **0** 即全透明，文字保持不透明。透明处在 Windows 上可能鼠标穿透，可按住顶部 **⠿** 按钮拖动。**置顶**单独开关，默认关闭。普通窗口保留原生标题栏。
- **背景取色**：偏好 → 浮窗背景色 → **桌面取色**，窗口暂时消失后单击目标颜色；`Esc` / 右键取消。也可使用 **选择颜色** 或 **跟随主题**。背景色仅在浮窗生效，文字随所选颜色切换深浅；完全透明时可根据实际桌面背景选用合适的主题或取色。取色是一次性采样，不会自动追踪桌面变化，屏幕图像只临时留在内存中，不保存或上传。
- **目录 / 最近**：展开或收起导航。紧凑窗口和浮窗默认收起，仍可手动展开。
- **隐藏**：有托盘时隐藏至托盘，否则最小化。托盘提供显示/隐藏、打开、设置、退出。关闭按钮默认隐藏至托盘，可在偏好中改为退出。
- **按键映射**：偏好中点击对应操作的“修改”，直接按下按键或组合键完成录入，`Esc` 取消；支持字母、数字、方向键、功能键、组合键，不局限于预设列表。支持上一页、下一页、专注模式、显示/隐藏和紧急退出。录入期间暂时暂停全局快捷键，完成或取消后恢复，避免修改时误触退出。检测重复映射；`Esc`、`Ctrl+O`、`Ctrl+,`、`Ctrl+C` 保留给退出专注、打开、偏好和复制。全局快捷键默认关闭，注册失败会提示。系统保留的组合可能无法录入或注册。
- **一键隐藏 / 显示**：默认 `Ctrl+Alt+R`，同一快捷键切换。若要在隐藏后或操作其他程序时使用，请在偏好勾选“启用全局显示 / 隐藏和紧急退出快捷键”。已有关闭全局快捷键的设置会保留。
- **紧急退出**：默认 `Ctrl+Alt+Q`，可在偏好录入修改；启用上述全局开关后，窗口隐藏或失去焦点时也生效。直接结束当前阅读器进程，绕过关闭到托盘和后台导入等待；会尝试保存当前位置，保存失败仍退出。正常退出仍可使用托盘菜单。旧设置如已占用默认退出键，会为新增退出操作选择不冲突的组合。
- TXT 自动识别 UTF-8 BOM、UTF-16 BOM 和可靠的 GB 系列编码；若无法确定，会提示手动选择。使用 **编码**重新读取 GB18030/GBK、UTF-16 LE/BE 等；不使用乱码替换符静默解码。

## 支持范围与限制

- TXT 文件名作为标题，识别常见中文章回及英文 Chapter / Part 标题。保留文字、合并多余空行，段落间距由阅读偏好控制。
- EPUB 读取标题、作者、spine 顺序和 EPUB 2 NCX / EPUB 3 导航中的章节标签，转为纯文本排版。**暂不显示封面、插图、复杂 CSS、原书版式或竖排**。同一 XHTML 内的多个目录锚点暂合并为一个章节。不执行 HTML / JavaScript，不请求外链。
- 拒绝加密资源（包括 DRM 和字体混淆）、损坏结构、异常压缩包及不安全路径；不提取 ZIP 到磁盘。
- 单文件上限 32 MiB；EPUB 总解压量上限 64 MiB、最多 4096 项。长章节按最多 24,000 字符分段，只排版当前分段；导入运行于后台线程。
- 正文按当前窗口尺寸和字体实际布局分页，位置保存为章节 ID + Unicode 文本偏移；若原文件被外部大幅修改，原位置可能只能近似恢复。
- 不扫描目录、不复制原书、不提供自动更新和数字签名。仅支持一个实例使用同一数据目录。

## 本地数据与恢复

默认使用 Qt 的 `AppLocalDataLocation`（Windows 通常在 `%LOCALAPPDATA%\QuietReader\QuietReader`）。可通过以下命令指定独立目录：

```powershell
.\.venv\Scripts\python.exe run.py --data-dir .\artifacts\my-state
```

`state.json` 仅记录最近 50 本书的路径/元数据、位置、窗口和设置，不保存正文。写入采用临时文件、fsync、原子替换，`state.backup.json` 保留上一版。主文件损坏时从备份恢复，并保留 `.damaged.json`；不支持的数据版本不会覆盖。路径只在本地状态中保存，错误提示不包含路径或正文。恢复失败或没有写权限时会提示。

## 开发、验证与打包

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/gui_smoke.py
.\.venv\Scripts\python.exe scripts/background_smoke.py
.\.venv\Scripts\python.exe scripts/focus_smoke.py
.\.venv\Scripts\python.exe scripts/preferences_smoke.py
.\scripts\build.ps1
.\.venv\Scripts\python.exe scripts/packaged_smoke.py
.\.venv\Scripts\python.exe scripts/packaged_smoke.py --focus
.\.venv\Scripts\python.exe scripts/packaged_smoke.py --emergency
```

`pytest` 使用离屏 Qt；各 GUI 冒烟脚本打开实际 Windows 窗口并使用原创临时测试数据，验证后自动关闭，截图和报告位于忽略的 `artifacts/`。默认打包产物：`dist\QuietReader\QuietReader.exe`，必须保留整个目录。如果该目录中的旧版仍在运行，构建脚本会自动输出到独立的 `dist\releases\...\QuietReader`，不清理使用中的目录。可通过 `scripts/build.ps1 -OutputRoot dist/focus-release` 指定仓库 dist 内的独立输出根目录。最新成功构建的 EXE 路径记录在 `artifacts/latest-build.txt`，打包冒烟默认验证此路径，也可用 `--exe` 指定。使用新版前从托盘退出旧版，以便接续同一份本地进度。签名、安装器和干净系统兼容性仍需后续验收。

目录职责：

```text
src/quietreader/
  domain/        文档、章节、语义位置、设置
  content/       受限 TXT / EPUB 导入
  persistence/   版本化状态、原子写入、备份恢复
  desktop/       Windows 全局热键、屏幕恢复
  ui/            阅读排版、窗口、主题与设置
tests/           核心单元与 Qt 交互回归
scripts/         GUI 冒烟、Windows 打包、原有技能检查
docs/            计划、架构决定、核验与验收记录
```

第三方使用与分发条件见 [依赖说明](docs/third-party.md)，测试结果与待验证场景见 [验收记录](docs/validation.md)。

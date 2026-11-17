# QuietReader 本地阅读器实施计划

## 已确认设计

用户于 2026-11-17 确认：采用 Python + PySide6，首版仅本地 TXT/EPUB，不接入 AnyReader。此决定优先于原规格的 Electron 推荐。使用仓库现有 `.venv`，不更换解释器。

- `src/quietreader/domain`：书籍、章节、语义位置、设置校验。
- `src/quietreader/content`：编码与 TXT/EPUB 导入，不执行书籍脚本，不访问网络。
- `src/quietreader/persistence`：版本化 JSON 状态，原子替换及备份；只保留路径、元数据和语义位置，不保存正文。
- `src/quietreader/ui`：Qt 原生纸页风格、QTextDocument 实际排版分页、目录、最近阅读与设置。
- `src/quietreader/desktop`：窗口可见区域恢复、托盘、Windows 全局热键。

EPUB 首版支持未加密的文字型 EPUB，按 spine 阅读顺序提取安全纯文本，不执行 HTML、脚本、外链，不承诺复杂 CSS、图片和原书版式。缺失目录用文档标题/文件名兜底。单文件上限 32 MiB，EPUB 解压总量上限 64 MiB，拒绝异常压缩包。

## 顺序与验收

1. 建立 pyproject、依赖及失败测试；安装到 `.venv`。检查命令：`.\.venv\Scripts\python.exe -m pytest`。
2. 实现 TXT 编码、章节解析、EPUB 元数据与安全边界；用内存构造 EPUB 和各编码样本验证。
3. 实现语义位置、设置迁移、原子存储与屏幕恢复；覆盖坏状态、备份恢复、无效设置和屏幕移除。
4. 实现 Qt 阅读窗口与后台导入、实际布局分页、目录/最近阅读跳转、设置、托盘及热键；QTest 验证导入、翻页、重新排版、重启恢复。
5. 使用现有 `.venv` 构建 Windows 目录包，运行离线 GUI 测试并检查截图；记录尚需 Windows 10/多显示器等人工验收项。
6. 检查完整改动，只提交本阶段文件；保留原 IDE 暂存项；按授权提交中文信息并推送 origin，遇到权限问题明确报告。

## 风险和后续

Qt 的背景透明度独立于文字透明度，面板设可读下限。窗口采用原生标题栏保证拖动、缩放及可访问性；浮窗模式显式切换，默认不置顶。日志与错误消息不包含书籍正文和路径。大文件后台读取，每次只对当前章节排版，长章节按段落分块。后续完整 EPUB 排版或 Python 业务扩展可替换导入/排版层。

## 本阶段结果

步骤 1–5 已执行：24 项测试、Windows GUI 冒烟和最终独立 EXE 冒烟通过；具体证据及未覆盖项见 `docs/validation.md`。步骤 6 的提交编号和同步结果随阶段交付报告提供。没有执行原指南中的在线集成或 Electron 提示词。

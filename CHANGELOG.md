# QuietReader 更新日志 / Changelog

## [0.1.5] — 2026-11-18

### 简体中文

本版本提供 Windows x64 便携软件包，适合直接解压运行。程序包含 TXT 与 EPUB 本地阅读、书架、目录和书签、排版偏好、专注模式等功能。具体支持范围见 [中文 README](README.md)。

#### 下载与运行

- 下载：[QuietReader-0.1.5-Windows-x64.zip](https://github.com/Nore07/Quiet-Reader/releases/download/v0.1.5/QuietReader-0.1.5-Windows-x64.zip)。
- SHA-256：`db34a63c31b847501ec2504e94c9ae96272efa27ef6ca91a9c877e21f022fc9b`；校验文件：[QuietReader-0.1.5-Windows-x64.zip.sha256](https://github.com/Nore07/Quiet-Reader/releases/download/v0.1.5/QuietReader-0.1.5-Windows-x64.zip.sha256)。
- 解压后运行 `QuietReader.exe`，并保留程序目录中的所有文件。
- 软件包包含应用程序、运行时依赖、Apache-2.0 许可文本和第三方许可信息（包括 CPython、Qt for Python、PyInstaller 及其他运行依赖）；不包含仓库源码、开发脚本、测试内容、个人设置或书籍。
- 当前 Windows 软件包未进行代码签名。

#### 配置与书籍位置

- 配置、阅读进度和书签：`data\state.json`。
- 书籍文件：`data\bookshelf\uncategorized\` 或 `data\bookshelf\<分类名>\`。
- `data` 位于阅读器根目录：源码运行时在仓库根目录下，Release 版在 `QuietReader.exe` 旁边。磁盘目录使用英文名称 `bookshelf` 和 `uncategorized`，界面名称由语言设置翻译。
- 源码版和 Release 版的数据目录相互独立；需要共享时，启动两者时使用相同的 `--data-dir <目录>`。
- 首次启动时，如果目标 `data` 为空，程序会把旧版 `%LOCALAPPDATA%\QuietReader\QuietReader\` 中的配置和书架副本迁移到新位置；旧目录会保留。
- 更新软件时保留原来的 `data` 文件夹。若解压到新目录，将旧目录中的 `data` 复制到新 `QuietReader.exe` 旁边。

#### 本次调整

- 改进窄窗口下的阅读翻页控件与书签操作按钮布局。
- 将配置和书架数据改为保存在应用根目录的 `data` 文件夹，并在默认路径首次启用时迁移旧数据。
- 书架与未分类文件夹在磁盘上使用稳定的英文名称，同时保留界面的中英文显示。

### English

This release provides a portable Windows x64 package. It includes local TXT and EPUB reading, a bookshelf, table of contents and bookmarks, reading layout preferences, and Focus Mode. See the [English README](README.en.md) for supported formats and features.

#### Download and run

- Download: [QuietReader-0.1.5-Windows-x64.zip](https://github.com/Nore07/Quiet-Reader/releases/download/v0.1.5/QuietReader-0.1.5-Windows-x64.zip).
- SHA-256: `db34a63c31b847501ec2504e94c9ae96272efa27ef6ca91a9c877e21f022fc9b`; checksum file: [QuietReader-0.1.5-Windows-x64.zip.sha256](https://github.com/Nore07/Quiet-Reader/releases/download/v0.1.5/QuietReader-0.1.5-Windows-x64.zip.sha256).
- Extract the archive, run `QuietReader.exe`, and keep every file in the application directory.
- The package contains the application, runtime dependencies, the Apache-2.0 license, and third-party notices for CPython, Qt for Python, PyInstaller, and other runtime dependencies. It excludes repository source, developer scripts, tests, personal settings, and books.
- This Windows package is not code-signed.

#### Settings and books

- Settings, reading positions, and bookmarks: `data\state.json`.
- Book files: `data\bookshelf\uncategorized\` or `data\bookshelf\<category>\`.
- `data` is under the reader root: under the repository root when run from source, and beside `QuietReader.exe` in a release. On-disk folder names are `bookshelf` and `uncategorized`; the interface translates their labels according to the selected language.
- Source and release builds keep separate data directories. To share data, launch both with the same `--data-dir <directory>`.
- On first launch, if the target `data` directory is empty, the app copies settings and bookshelf files from the previous `%LOCALAPPDATA%\QuietReader\QuietReader\` location. The old directory is retained.
- Keep the existing `data` folder when updating. If you extract into a new location, copy the old `data` folder beside the new `QuietReader.exe`.

#### Changes

- Improved reader navigation and bookmark action layouts in narrow windows.
- Moved settings and bookshelf data to the application-root `data` folder, with first-run migration from the previous default location.
- Standardized on-disk bookshelf folder names in English while keeping translated interface labels.

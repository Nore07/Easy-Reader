# QuietReader · 静读

**QuietReader** is an offline-first Windows reader for local TXT and reflowable EPUB books. It is built with Python and PySide6. Your books and reading progress stay on your computer; the app has no online book sources, telemetry, or account service.

QuietReader 是一款 Windows 本地 TXT / EPUB 阅读器，使用 Python + PySide6 开发。书籍、阅读进度和设置都保存在本机；应用不联网抓取书源，也不包含遥测或账户服务。

## Windows portable package

Published Windows ZIPs, when available, will be listed on [GitHub Releases](https://github.com/Nore07/Easy-Reader/releases). Extract the **entire** archive, then run `QuietReader\QuietReader.exe`; keep the included files together because the executable depends on its Qt runtime files. If no build is listed yet, use the source-build steps below.

已发布的 Windows ZIP 会列在 [GitHub Releases](https://github.com/Nore07/Easy-Reader/releases)。解压整个压缩包后运行 `QuietReader\QuietReader.exe`，并保留目录中的全部文件；程序需要随包提供的 Qt 运行组件。如果 Releases 暂无安装包，可按下方步骤从源码构建。

## Features

- Read local TXT and unencrypted, reflowable EPUB files, including common EPUB illustrations, tables of contents, internal links, and print page lists.
- Organize books into a local bookshelf, recent reading, and user-created categories. Adding a book copies it into the bookshelf and leaves the original file untouched.
- Use bookmarks and notes, book metadata and covers, adjustable typography, Chinese or English UI, light/dark/sepia themes, and configurable keyboard shortcuts.
- Focus mode removes the reader chrome and supports a transparent or sampled desktop-color background.
- Resume reading from the last saved position. The app does not upload book content or local state.

## Run or build from source (Windows)

Requires Python 3.12 or newer. In PowerShell, from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install ".[build]"
.\.venv\Scripts\python.exe run.py
```

To build a portable onedir package:

```powershell
.\scripts\build.ps1 -OutputRoot dist/releases/0.1.0
```

The executable and its required runtime files are written to `dist/releases/0.1.0/QuietReader/`.

## Supported formats and limits

- TXT: common UTF-8, UTF-16 and Chinese encodings; manual encoding selection is available.
- EPUB: unencrypted reflowable EPUB 2/3 with common navigation, metadata, covers, formatting and local illustrations.
- DRM, fixed-layout EPUB, arbitrary publisher CSS, active content, external resources and online sources are not supported.

Application data is stored locally under Qt's `AppLocalDataLocation` (normally `%LOCALAPPDATA%\QuietReader\QuietReader` on Windows). Books added to the shelf are copied into that data folder.

## Licensing

The project source does not yet include a selected open-source license. Until one is added, viewing the source does not grant permission to redistribute or reuse it. Third-party dependency notices and distribution notes are in [`docs/third-party.md`](docs/third-party.md).

# 依赖与分发

项目目前没有替用户选定自编代码的开源许可证；发布前需作决定。AnyReader 未链接、未复制、未安装，不属于运行依赖。

| 组件 | 用途 | 上游许可证 / 依据 |
| --- | --- | --- |
| PySide6 / Qt | 桌面窗口与文字布局 | LGPLv3 / GPLv3 / 商业许可选项，见 [官方许可说明](https://doc.qt.io/qtforpython-6/licenses.html) |
| charset-normalizer | 编码识别 | MIT，见 [上游](https://github.com/jawah/charset_normalizer) |
| defusedxml | 限制 XML 实体等攻击 | PSF，见 [上游](https://github.com/tiran/defusedxml) |
| PyInstaller | 开发期打包 | GPL 带引导程序分发例外，见 [许可](https://pyinstaller.org/en/stable/license.html) |

当前运行仅导入 PySide6 Essentials 的 QtCore、QtGui、QtWidgets；打包工具还会收集 Qt 的运行依赖。QtTest 只用于开发测试。打包采用 onedir，Qt 动态库独立保留，不使用静态链接。构建脚本将已安装 wheel 的许可通知和许可元数据复制到 `third-party/`。本次 PySide6 Essentials 的元数据声明 LGPL/GPL 选项，但 wheel 的 licenses 目录仅附商业许可说明；不能据此宣称通知完整。对外发布时仍需从对应版本上游补全许可文本，核对完整第三方通知、Qt 库替换能力及对应源码提供义务。当前为未签名本地测试包。

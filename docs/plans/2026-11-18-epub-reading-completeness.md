# 常见 EPUB 阅读能力

## 目标与边界

补齐常见 EPUB 重排版阅读体验。首阶段明确支持独立的上一页/下一页、上一章/下一章、带层级的 EPUB 目录、书内锚点跳转和可选的印刷页码列表。后续阶段增加阅读标记、书籍封面/元数据呈现和安全的基础文本语义排版。

“常见阅读功能”不等于实现 EPUB 的全部规范。固定版式、脚本、音视频、媒体覆盖、DRM、外部网络资源、任意 CSS、竖排和复杂 MathML 暂不纳入；导入器继续不执行书籍脚本、不发网络请求，并对所有 ZIP/XML/图片资源维持现有限额。

规范依据：EPUB 3.3 以 spine 表示默认阅读顺序；导航文档可包含层级 toc、可选 page-list 和 landmarks。页码目标与正文片段链接都使用文档路径加片段标识。EPUB Reading Systems 3.3 要求呈现目录链接并提供到达目标的导航。[EPUB 3.3](https://www.w3.org/TR/epub-33/) · [EPUB Reading Systems 3.3](https://www.w3.org/TR/epub-rs-33/)

## 阶段一：章节和 EPUB 书内导航

### 改动范围

- `src/quietreader/domain/models.py`：添加内存中的导航条目、锚点和书内链接模型，保持既有 `Book` / `Section` 构造兼容。
- `src/quietreader/content/local.py`：读取 EPUB 3 nav toc/page-list/landmarks 和 EPUB 2 NCX 层级；在清洁文本抽取期间保留 id/name 锚点、内部链接和 `pagebreak` 位置；解析相对 ZIP 路径与 URL 片段但绝不访问外网；在章节拆块后修正字符偏移。
- `src/quietreader/ui/window.py`、`src/quietreader/ui/reader.py`：加入独立上一章/下一章操作；现有翻页在章节边界继续连读。目录层级和页码列表通过可靠的章节/字符偏移跳转；正文内部链接可点击。未知、外部、损坏和非 spine 目标安全忽略或给出本地提示。
- `src/quietreader/keys.py`、`src/quietreader/domain/models.py`、`src/quietreader/ui/settings.py`、`src/quietreader/i18n.py`：为上一章/下一章提供可修改的键盘映射并检查冲突。

### 完成条件与验证

- 构造 EPUB3 目录（嵌套章节和 `chapter.xhtml#id`）、page-list、跨章节脚注链接以及正文 pagebreak 样本，验证路径解码、fragment 偏移和章节拆分的语义位置。
- 构造 EPUB2 NCX 嵌套 navPoint 样本并验证顺序和层级。
- Qt 行为测试覆盖上一页/下一页、上一章/下一章、边界禁用与内部链接跳转。
- 运行 `\.venv\Scripts\python.exe -m pytest -q`、Windows 导航 GUI 冒烟和构建后的独立程序验证。

## 阶段二：书签与书籍资料

### 改动范围

- 为书籍元数据保留标识符、语言、出版信息、封面资源引用和 EPUB 内导航地标。
- 允许在当前位置添加/删除书签并从列表恢复章节/字符偏移；保存格式做向后兼容迁移，只存本地状态，不复制原书内容。
- 以安全的本地图片资源显示封面，缺失/无效封面时回退到书名和作者。

### 完成条件与验证

- EPUB2/EPUB3 封面元数据回退、目录地标、缺失/损坏封面和书签 CRUD、重启恢复测试。
- 确认旧版 state.json 可读，备份与未来版本保护行为不退化；运行全套 pytest 和独立 EXE 冒烟。

## 阶段三：基础 EPUB 文本语义排版

### 改动范围

- 从安全解析后的内容保留标题层级、段落、强调、粗体、删除线、引用、列表、行内代码、上标/下标和水平分隔线等常见语义。
- 仅把已提取的安全文本与受限格式标记交给 Qt 文档；不让原始 XHTML/CSS/脚本进入富文本渲染器。
- 继续支持图文序列、可读的目录标题和语义位置恢复；明确处理不支持的 MathML/复杂排版。

### 完成条件与验证

- 语义标记测试覆盖嵌套标签、实体、脚本/样式内容排除、分块边界以及书页实际格式。
- 运行全套 pytest、图文与导航 GUI 冒烟、独立 EXE 打包回归；更新 README 支持范围及限制。

## 执行顺序

1. 先为阶段一导入与导航行为编写失败测试，再实现数据流和界面操作。
2. 每阶段完成后复核当前分支、暂存明确文件、运行对应验证、提交并推送到 `origin/main`。
3. 不接触用户原书和当前运行的旧程序；GUI/打包测试使用临时生成的 EPUB 与独立输出目录。

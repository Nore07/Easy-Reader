# AnyReader Core 核验

核验日期：2026-11-17。用户指定来源：<https://github.com/aooiuu/any-reader>。

## 结论

当前不安装、不打包、不执行 Core 或来源规则。先交付本地阅读；在线入口明确显示未启用。不存在已经验证可用的在线来源。

## 已确认事实

- 官方 npm 包 `@any-reader/core` 查询版本为 `1.11.12`，包的 repository 指向用户给出的仓库。尚未锁定源码提交，因此 master 链接仅作调研依据。
- [包配置](https://github.com/aooiuu/any-reader/blob/master/packages/core/package.json)声明 `GPL3`；[仓库许可证](https://github.com/aooiuu/any-reader/blob/master/LICENSE)为 GNU GPL 第三版文本。后续分发需要评估整个组合程序的源码提供、许可证及通知义务；本记录不代替法律意见。当前自编代码未链接或复制 Core。
- 包导出 Node CJS/ESM 及 browser 入口，附 TypeScript 类型，构建命令为 `unbuild`。依赖包含 workspace 包、Axios、Puppeteer 等；不能据此认定可直接打包到 Electron。
- [公开入口](https://github.com/aooiuu/any-reader/blob/master/packages/core/src/index.ts)导出 `createRuleManager`。它接收规则及可选 analyzer；规则可涉及 JavaScript 执行，不能允许不可信规则在主进程中直接运行。
- [README](https://github.com/aooiuu/any-reader/blob/master/packages/core/README.md)列出搜索、目录及正文能力；[RuleManager 源码](https://github.com/aooiuu/any-reader/blob/master/packages/core/src/analyzer/RuleManager.ts)中的搜索是异步方法。README 的简写不能直接当作完整类型签名。

## 未核验及阻塞项

| 项目 | 当前状态 / 后续完成条件 |
| --- | --- |
| 精确提交与发布产物一致性 | 未验证；下载锁定版本、核对类型及许可证 |
| 初始化、搜索、目录、正文 | 未运行最小程序；需要授权测试规则与来源 |
| 登录与令牌存储 | 未确认公开契约，不实现 |
| 来源授权、限速、缓存、地域限制 | 没有指定合法来源，不预置规则、不联网抓取 |
| Windows / Electron 打包 | 未验证 Puppeteer、浏览器下载及运行隔离 |
| 测试覆盖、维护状态 | 没有运行上游测试，不能凭网页抓取日期判断活跃程度 |
| 许可证兼容 | 尚未决定产品分发许可证，接入前明确 GPL 义务与第三方通知 |

未来接入顺序：锁定版本 → 许可决定 → 授权来源 → 独立受限进程的离线最小验证 → 网络与权限白名单 → 错误映射与打包回归。保留 ContentProvider 边界，不虚构 API，不把来源脚本注入阅读界面。

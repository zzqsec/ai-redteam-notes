# AI Redteam Notes

> 🤖 AI 驱动的红队免杀知识库 — 合法授权的渗透测试与安全研究
>
> 🛠️ Powered by **QwenPaw Desktop** + **DeepSeek V4 Pro**<br>
> 🛠️ Powered by **Claude Code** + **DeepSeek V4 Pro**

✅ **不要偷偷用！点个star在开始~**✅

工作繁忙，暂停更新，等待恢复！

---

## 这是什么

这是一个 **AI 辅助生成** 的红队对抗技术笔记仓库。内容涵盖 Webshell 免杀、WAF/RASP/EDR 绕过、流量伪装等实战技术点。所有内容均由 AI 根据真实攻防经验整理、归纳、输出，再由人工验证后归档。

**核心理念**：不是堆砌工具和脚本，而是把每种绕过技术的**原理、适用场景、限制条件**讲清楚 — 让读者理解"为什么能绕过"而不是只会复制粘贴。

---

## 当前内容

### 📄 PHP 免杀技术点清单 ✅ 实战验证

PHP Webshell 生成的完整方法论，包含：

| 模块 | 内容 |
|------|------|
| **6 套技术方案** | gzip+base64 嵌套、动态函数名拼接、回调高阶函数、注释断裂+标签嵌套、RASP 专项绕过、协议上下文逃逸 |
| **组合策略** | 针对安全狗/云锁/长亭牧云/OpenRASP 的最优方案组合 |
| **哥斯拉 V3 微步 TDP 专项** | `include + tempnam` 替代 `eval`、左右追加随机字节、Header 验证、两阶段协议 MD5 前后缀避坑 |
| **实战踩坑清单** | 7 个典型翻车场景 + 根因 + 正确做法 |

每一步都标注了 **PHP 版本兼容性** 和 **绕过目标产品**。

---

### 📄 AdaptixC2 BOF 插件编写指南 ✅ 实战验证

从 CS (Cobalt Strike) 移植 BOF 到 AdaptixC2 的完整教程，包含：

| 模块 | 内容 |
|------|------|
| **基础概念** | BOF/Beacon/AxScript 是什么、AdaptixC2 对 CS BOF 的兼容边界 |
| **项目结构** | 标准目录布局 + BOF 命名规范 |
| **AxScript 全解** | 命令注册、参数打包、PreHook/PostHook 编写、右键菜单 |
| **CS → AdaptixC2 映射表** | `bof_pack` 类型对照（`Z`→`wstr` 等）、API 一一对应 |
| **BOF 参数打包** | 5 种类型的含义与选型、字符串乱码根因与修复 |
| **踩坑清单** | Command not found / 用户名乱码 / menu.add() 报错 等经典问题 |
| **完整模板** | 可直接复用的 `.axs` 脚本骨架 |

配套实战案例：AddUser-BOF（NetUserAdd + SAMR 双路径）的完整移植。

---

### 📄 Java 免杀技术点清单 ✅ 实战验证

> ✅ **已实测：JDK 1.8.0_181 + Tomcat 9.0.74，哥斯拉兼容 Webshell 六层全开版通过验证。**
>
> JDK 8/11/17 兼容性差异、Tomcat 7/8/9/10/11 版本差异均已整理，含 8 条实战踩坑记录。

Java Webshell + 内存马的技术框架，包含：

| 模块 | 内容 |
|------|------|
| **6 套 Webshell 方案** | 多层嵌套反射 + 动态类名拼接、BCEL 字节码加载、URLClassLoader 远程加载、AES 混淆解密、JSPX XML 注入、**哥斯拉兼容六层全开版（新增）** |
| **5 种内存马** | Filter 型 / Servlet 型 / Listener 型 / Controller 型（Spring）/ Valve 型（底层） |
| **JDK 版本兼容** | JDK 8 / 11 / 17 逐版本：包名差异、反射限制、Base64 API 兼容性 |
| **Tomcat 版本兼容** | Tomcat 7 / 8 / 9 / 10 / 11 逐版本：Servlet API 版本、包名变化（javax → jakarta）、调试注意事项 |
| **坑点记录** | 8 条实战踩坑（ClassLoader 不可替换 / 反调试放行 jdwp / 左右数据流失败 / 加密器选型 等） |
| **高阶对抗** | 类加载器隔离、反射链混淆、内存特征抹除、动态触发条件、环境感知、反调试检测 |
| **方案组合** | A+B 三重叠加 / A+C 远程加载 / D+Filter 内存马 / Controller+Valve 双绕过 |

每项标注了 **JDK 版本差异** 和 **目标中间件适配**。

---

### 📄 Ghost Bits (Cast Attack) 技术总结

> 来源：Black Hat Asia 2026 — 浅蓝 @ AlibabaCloud

Java `char` 是 16 位，但大量 API 只取低 8 位，**高位被静默丢弃**——利用这个特性可构造不同解析器看到不同内容的攻击。涵盖：

| 模块 | 内容 |
|------|------|
| **9 种攻击技术** | BCEL ClassLoader 绕过、Jackson SQLi、Fastjson `\u`/`\x` 转义、Tomcat 文件上传、全角 URL 路径穿越、JDK Base64 解码、GeoServer RCE 绕过、Jetty 二次编码、SMTP 协议注入 |
| **Ghost Bit 字符映射表** | 10 组 Unicode → ASCII 的单向映射（`.` `/` `0`-`9` `e` `j` `%` 等） |
| **4 个 CVE** | CVE-2025-41242 (Spring)、CVE-2025-7962 (SMTP)、CVE-2026-21933 (JDK)、CVE-2024-36401 (GeoServer) |
| **渗透实战** | 立即可用的 Payload 模板 + 自动化扫描脚本 + 代码审计关注点 |
| **供应链发现** | ActiveJ / Lettuce / XMLWriter / Jodd 等组件的 Ghost Bits 漏洞 |

---

### 📄 360 QVM 免杀技术手册 ✅ 实战验证

> 实测：2026-05-12，360 安全卫士最新版

针对 360 QVM AI 引擎 + 鲲鹏行为沙箱 + 云查杀的完整对抗手册，包含：

| 模块 | 内容 |
|------|------|
| **QVM 7大特征维度** | F1-F7 完整还原（n-gram / 熵分布 / IAT / CFG / PE结构 / 资源语义 / 元数据），含权重与精确对抗方法 |
| **5 种冷门执行技术** | Freeze 模式 NTDLL syscall / ETW Provider Patching + NtContinue / Atom Table 注入 / WinSAT DLL 劫持 / GDI Bitmap 共享内存 |
| **UUID 降熵编码** | shellcode → UUID 字符串，熵值从 7.8 降至正常区间，含 Windows 端序修正方案 |
| **全维度对抗成功率** | 1,247 个样本实测数据：F1-F7 全覆盖 → QVM 绕过率 **97.2%** |
| **完整攻击链** | CS → UUID 编码 → VS2022 编译 → 图标+签名包装 → 一键上线 |
| **反沙箱** | 内存/CPU/磁盘检测 + 120s 延时绕过鲲鹏沙箱 |

---

### 📄 Impacket PowerShell 绕过技术手册 ✅ 实战验证

> **状态：三工具 cmd/PS 全通 ✅ | AMSI bypass v3 ✅ | Win2022+Defender 通过 ✅**

Impacket (wmiexec/smbexec/dcomexec) PowerShell 执行特征分析与绕过改造方案，包含：

| 模块 | 内容 |
|------|------|
| **检测面分析** | 工具执行路径、PS 命令模板特征、检测层矩阵（YARA/ScriptBlock/AMSI/CLM/SMB/DCOM） |
| **绕过技术** | BXOR 编码替代 Base64、AMSI Bypass v3（混淆 context-zeroing）、`-Enc` 统一传输 |
| **实际改造记录** | `evasive_encoder.py` 新增 + smbexec/wmiexec/dcomexec 三工具改造（每工具 ~8 行） |
| **⚠️ 已知限制** | SMB 管道名不可随机化；PS 2.0 不兼容 BXOR |
| **踩坑清单** | 10 条踩坑记录（`-Command` 引号、name mangling、VirtualProtect 行为检测等） |
| **验证环境** | Win2022 + Defender ✅ | Win2008 R2（无 AMSI，cmd 模式全通） |

---

### 📄 fscan 免杀特征点与解决技术手册 ✅ 实战验证

> 实测：2026-05-17，火绒 V5.x + 360 V15.x + Defender

fscan 内网扫描器针对火绒/360/Defender 的完整免杀方案，包含：

| 模块 | 内容 |
|------|------|
| **火绒 vs 360 vs Defender 检测差异** | 火绒认 Go PE 结构（rt0 入口 + pclntab magic + 节区名），360/Defender 认 UPX 解压后 `.rdata` 明文字符串 |
| **5 套方案** | A 编译+PE清洗 / B Garble混淆+PE清洗 / **C DLL化（主战）** / E strip+PE清洗 / F 源码字符串全量去特征 |
| **PE 清洗四步流程** | wipe_runtime_metadata → normalize_section_names → strip_fingerprints → save |
| **一键构建脚本** | `build_all.bat` 批量编译五方案，自动化出活 |
| **核心结论** | 五方案无壳全过火绒+360+Defender；**一加 UPX，360 全部查杀** |
| **踩坑清单** | 12 条（UPX 是最大坑、go-strip 不兼容 Go 1.26、c-archive `runtime/cgo` 缺失、`//go:embed` 嵌入资源替换 等）|

每套方案标注了**产物体积、目录位置、编译命令、对抗覆盖矩阵**。

---

### 📄 BYOVD BootRepair.sys EDR Killer ✅ 实战验证

> 实测：2026-05-24，Win10 — 火绒 V5.x + 360 V15.x

利用 Lenovo BootRepair.sys 签名驱动无 DACL 漏洞，IOCTL 0x222014 内核级终止任意进程的完整实战指南，包含：

| 模块 | 内容 |
|------|------|
| **驱动逆向分析** | DriverEntry → IoCreateDevice（无 DACL）→ IRP_MJ_DEVICE_CONTROL → 单 IOCTL 0x222014 → ZwTerminateProcess |
| **武器化 PoC** | 完整 C 源码，支持 PID/进程名两种模式，编译即用 |
| **实战测试** | 火绒 `HipsDaemon.exe` ✅ 一杀就死 | 360 `ZhuDongFangYu.exe` ✅ 能杀但 ~1 分钟自拉活 |
| **360 循环 Kill** | batch / C 双版本循环杀脚本，持续压制 360 守护进程 |
| **BYOVD 狩猎方法论** | 厂商白驱动收集 → 批量逆向筛选（有签名+无 DACL+高危 IOCTL）→ 武器化 |
| **攻击链** | 管理员加载驱动 → 任意用户打开设备 → DeviceIoControl(0x222014, PID) → 内核杀进程 |

---

## 📦 更新日志

| 日期 | 内容 |
|------|------|
| 2026-05-24 | `BYOVD BootRepair.sys EDR Killer` ✅ 实战验证 — 联想签名驱动无 DACL 漏洞武器化，火绒/360 实战测试 |
| 2026-05-17 | `fscan 免杀特征点与解决技术手册` v1.2 ✅ 实战验证 — 一键构建脚本细化（Go原生PE清洗器/embed扫描/XOR插件名混淆/并行编译）|
| 2026-05-16 | `Impacket PowerShell 绕过技术手册` v1.2 重构 — 394→155 行精简；AMSI bypass v3 混淆版（context-zeroing）；三工具 `-Enc` 统一改造；Win2022+Defender 全链路验证通过 |
| 2026-05-16 | `Impacket PowerShell 绕过技术手册` v1.0 — ETW bypass + BXOR 链通过 Win10+Defender 验证；Win2008 R2 全工具 cmd 模式验证通过 |
| 2026-05-16 | `AdaptixC2 BOF 插件编写指南` ✅ 实战验证 |
| 2026-05-15 | `Java免杀技术点清单` ✅ 实战验证 — 新增哥斯拉六层全开方案F、JDK/Tomcat版本兼容详情、8条坑点记录 |
| 2026-05-12 | 新增 `360 QVM 免杀技术手册` ✅ 实战验证 — QVM 7大特征维度还原 + 5 种冷门执行 + 全维度绕过率 97.2% |
| 2026-05-12 | 新增 `Ghost Bits 技术总结` — Black Hat Asia 2026 · 9 种攻击技术 + 4 CVE + 渗透实战指南 |
| 2026-05-12 | 新增 `AdaptixC2 BOF 插件编写指南` — CS → AdaptixC2 BOF 移植全流程 + 踩坑清单 |
| 2026-05-12 | 初始提交 `PHP 免杀技术点清单` ✅ 实战验证 — 6 套方案 + 哥斯拉 V3 微步 TDP 绕过 + 实战踩坑 |

---

## 为什么叫 "AI Redteam"

- **生成方式**：所有文档均由 AI 根据安全研究经验生成初稿，人工审核修正
- **迭代速度**：AI 能快速穷举绕过思路的变体，人负责验证和筛选
- **可复现**：Prompt 即方法论 — 同样的提示词框架可以迁移到其他语言/场景

这本质是一套 **"人定策略，AI 出内容"** 的安全知识生产流水线。

---

## 免责声明

⚠️ 本仓库所有内容仅限 **合法授权的渗透测试** 与 **安全研究** 使用。

禁止用于任何未经授权的入侵、破坏或非法活动。使用者须自行承担一切法律后果。

---

## 贡献

欢迎 PR。如果你有经过验证的绕过技术想收录，请附带：

1. 技术原理说明
2. 版本兼容性
3. 绕过目标产品及版本

AI 生成的内容也欢迎 — 但必须标注"AI 生成"并经过人工验证。

---

## 许可

CC BY-NC-SA 4.0 — 学习交流自由。

> 致敬所有在免杀对抗领域默默耕耘的前辈 — 站在巨人的肩膀上，我们才能看得更远。

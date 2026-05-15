# AI Redteam Notes

> 🤖 AI 驱动的红队免杀知识库 — 合法授权的渗透测试与安全研究
>
> 🛠️ Powered by **QwenPaw Desktop** + **DeepSeek V4 Pro**

---

## 这是什么

这是一个 **AI 辅助生成** 的红队对抗技术笔记仓库。内容涵盖 Webshell 免杀、WAF/RASP/EDR 绕过、流量伪装等实战技术点。所有内容均由 AI 根据真实攻防经验整理、归纳、输出，再由人工验证后归档。

**核心理念**：不是堆砌工具和脚本，而是把每种绕过技术的**原理、适用场景、限制条件**讲清楚 — 让读者理解"为什么能绕过"而不是只会复制粘贴。

---

## 当前内容

### 📄 微步TDP全链路绕过技术手册 ✅

微步TDP威胁检测平台全链路检测机制与绕过，8维度深度分析：

| 模块 | 内容 |
|------|------|
| **架构全景** | 采集层(eBPF/ETW)/分析层(Kafka+Flink)/响应层(SOAR)/Agent对比 |
| **静态检测引擎** | YARA规则库/熵值算法/PE结构校验，含Python脚本 |
| **沙箱动态分析** | 超时/反沙箱检测/API Hook，含C++抗检测代码 |
| **流量检测** | DPI/TLS解密/JA3指纹/Beacon检测，含Python分析脚本 |
| **ML模型** | 特征工程(静态/动态/流量/图特征)/对抗样本(FGSM/PGD) |
| **Webshell专项** | 静态规则/OPCode分析/熵值权重三层检测及绕过 |
| **实战绕过矩阵** | PHP/哥斯拉/冰蝎代码级绕过方案 |
| **差异化对抗** | TDP vs 360 vs Defender 对比策略 |

---

### 📄 Impacket PowerShell 绕过技术 ✅

Impacket 工具集 PowerShell 全链路特征拆解与绕过：

| 模块 | 内容 |
|------|------|
| **6种执行路径** | psexec/smbexec/wmiexec/dcomexec/atexec/注册表 — 各自PS脚本特征差异 |
| **AV/EDR检测** | ScriptBlock日志/AMSI拦截/CLM约束/ETW/参数编码检测 |
| **源码分析** | 精确到文件+函数+行号的修改点 |
| **绕过矩阵** | BXOR+Int16编码/ScriptBlock::Create替代iex/Base58+Z85编码轮换/AMSI+CLM组合 |
| **流量特征** | SMB命名管道/DCOM CLSID指纹/135端口行为 + Suricata规则 |
| **源码修改方案** | EvasivePayloadEncoder Python类 + 一键patch脚本 |

#### psexec.py 7维度专项 + 5个实战修改方案

| 方案 | 耗时 | 绕过效果 |
|------|------|---------|
| 服务名随机化 | 5分钟 | 绕过事件日志IOC |
| 管道名伪装 | 10分钟 | 绕过Suricata/Zeek流量规则 |
| 自编译exe替换 | 30分钟 | Defender/360哈希查杀绕过 |
| WMI替代服务 | 1-2小时 | 无7045/4697事件 |
| Shellcode Loader | 3-5小时 | 无cmd/powershell进程链 |

---

### 📄 ADCS PKI 攻击链技术手册 ✅

Active Directory Certificate Services 攻击链，11维度全覆盖：

| 模块 | 内容 |
|------|------|
| **架构全景** | CA角色/模板/AIA/CDP/Forest Trust + 攻击面映射 |
| **ESC全矩阵** | ESC1-ESC13 每个漏洞的Certipy命令+利用条件+影响 |
| **模板攻击面** | CT_FLAG标志位 + Python模板审计脚本 |
| **NDES/SCEP** | 接口利用 + Python POC + 防御配置 |
| **Web Enrollment** | DLL侧加载/Path Traversal + IIS硬化脚本 |
| **PKINIT** | 完整Python实现核心逻辑 |
| **NTLM中继** | ESC8/ESC10/ESC13 + Python自动化框架 |
| **检测防御** | Event 4886/4887/4898 + Sysmon + Sigma + 安全基线 |
| **工具对比** | Certipy vs Certify vs Pkinit vs 手搓Python |
| **ESC组合链** | ESC1+ESC8/ESC3+ESC9叠加攻击 |
| **提权路径** | 3条DA路径（成功率85%/70%/90%） |

---

### 📄 PHP 免杀技术点清单

PHP Webshell 生成的完整方法论，包含：

| 模块 | 内容 |
|------|------|
| **6 套技术方案** | gzip+base64 嵌套、动态函数名拼接、回调高阶函数、注释断裂+标签嵌套、RASP 专项绕过、协议上下文逃逸 |
| **组合策略** | 针对安全狗/云锁/长亭牧云/OpenRASP 的最优方案组合 |
| **哥斯拉 V3 微步 TDP 专项** | `include + tempnam` 替代 `eval`、左右追加随机字节、Header 验证、两阶段协议 MD5 前后缀避坑 |
| **实战踩坑清单** | 7 个典型翻车场景 + 根因 + 正确做法 |

每一步都标注了 **PHP 版本兼容性** 和 **绕过目标产品**。

---

### 📄 AdaptixC2 BOF 插件编写指南

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

---

## 📦 更新日志

| 日期 | 内容 |
|------|------|
| 2026-05-15 | `Java免杀技术点清单` ✅ 实战验证 — 新增哥斯拉六层全开方案F、JDK/Tomcat版本兼容详情、8条坑点记录 |
| 2026-05-14 | 新增 `微步TDP全链路绕过技术手册` ✅ N1 PRO MAX FLASH — 8维度TDP全链路检测机制与绕过 |
| 2026-05-14 | 新增 `Impacket_PowerShell绕过技术` ✅ N1 PRO MAX FLASH — Impacket全工具PS特征+绕过矩阵+psexec专项+5个实战修改方案 |
| 2026-05-14 | 新增 `ADCS_PKI攻击链技术手册` ✅ N1 PRO MAX FLASH — ESC1-ESC13全矩阵+3条DA路径+Python自动化框架 |
| 2026-05-12 | 新增 `360 QVM 免杀技术手册` ✅ 实战验证 — QVM 7大特征维度还原 + 5 种冷门执行 + 全维度绕过率 97.2% |
| 2026-05-12 | 新增 `Ghost Bits 技术总结` — Black Hat Asia 2026 · 9 种攻击技术 + 4 CVE + 渗透实战指南 |
| 2026-05-12 | 新增 `AdaptixC2 BOF 插件编写指南` — CS → AdaptixC2 BOF 移植全流程 + 踩坑清单 |
| 2026-05-12 | 初始提交 `PHP 免杀技术点清单` — 6 套方案 + 哥斯拉 V3 微步 TDP 绕过 + 实战踩坑 |

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
2. PHP 版本兼容性
3. 绕过目标产品及版本
4. 验证截图或日志

AI 生成的内容也欢迎 — 但必须标注"AI 生成"并经过人工验证。

---

## 许可

MIT License — 研究自由，后果自负。

> 致敬所有在免杀对抗领域默默耕耘的前辈 — 站在巨人的肩膀上，我们才能看得更远。

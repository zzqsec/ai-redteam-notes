# AdaptixC2 v1.2 深度源码分析报告

> 分析日期: 2026-05-19
> 源码版本: v1.2 (fork: https://github.com/zzqsec/AdaptixC2)
> 分析范围: AdaptixServer (Go) + AdaptixClient (C++ Qt6) + Extenders 插件体系

---

## 一、总体架构

AdaptixC2 采用 Server/Client 架构，服务端 Go (Gin + WebSocket)，客户端 C++ Qt6，通过 Extender 插件体系实现 Listener/Agent/Service 的可扩展性。

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│      AdaptixClient (C++)    │     │     AdaptixServer (Go)       │
│      Qt6 + C++23            │◄───►│     Gin + WebSocket          │
│                             │WSS  │                              │
│  ┌───────────────────────┐ │JWT  │  ┌────────────────────────┐  │
│  │ MainAdaptix (root)    │ │OTP  │  │ core/connector/        │  │
│  │  ├─ MainUI (QMainWin) │ │     │  │  └─ REST + WS API     │  │
│  │  ├─ Storage (SQLite)  │ │     │  ├─ core/server/         │  │
│  │  ├─ Extender (plugin) │ │     │  │  └─ Teamserver (核心) │  │
│  │  └─ Settings          │ │     │  ├─ core/database/       │  │
│  └───────────────────────┘ │     │  │  └─ SQLite 持久化     │  │
│                             │     │  ├─ core/eventing/       │  │
│  AdaptixWidget (per项目)   │     │  │  └─ Hook/Event 系统   │  │
│  ├─ SessionsTable          │     │  ├─ core/axscript/       │  │
│  ├─ ConsoleWidget          │     │  │  └─ JS 脚本引擎       │  │
│  ├─ TasksWidget            │     │  ├─ core/extender/       │  │
│  ├─ DownloadsWidget        │     │  │  └─ Go Plugin 加载器  │  │
│  ├─ ListenersWidget        │     │  └─ core/profile/        │  │
│  ├─ SessionsGraph          │     │     └─ YAML 配置解析     │  │
│  └─ ...其他Docks           │     │                              │  │
└─────────────────────────────┘     └──────────────────────────────┘
                                              │
                                    ┌─────────┴──────────┐
                                    │  extenders/ (插件)  │
                                    │  ├─ beacon_agent    │
                                    │  ├─ beacon_listener_*
                                    │  ├─ gopher_agent    │
                                    │  └─ gopher_listener_*
                                    └────────────────────┘
```

### 目录结构

```
AdaptixC2/
├── AdaptixServer/                     # Go 服务端
│   ├── main.go                        # 入口
│   ├── core/
│   │   ├── server/                    # 核心中枢 (Teamserver)
│   │   │   ├── server.go              # NewTeamserver(), Start(), RestoreData()
│   │   │   ├── utils.go               # Agent, Listener, Tunnel 结构体
│   │   │   ├── ts_agent.go            # Agent CRUD + 命令分发
│   │   │   ├── ts_listeners.go        # Listener 管理
│   │   │   ├── ts_tasks.go            # 任务管理
│   │   │   ├── ts_tunnels.go          # 隧道/SOCKS/端口转发
│   │   │   ├── ts_sync.go             # 客户端同步 (16类)
│   │   │   ├── mgr_broker.go          # WebSocket 消息广播
│   │   │   ├── mgr_task.go            # 任务管理器 (3种Handler)
│   │   │   └── mgr_tunnel.go          # 隧道管理器
│   │   ├── connector/                 # HTTP/WebSocket API
│   │   │   ├── connector.go           # TsConnector, TLS 配置
│   │   │   ├── tc_client.go           # 登录 JWT, WebSocket 连接
│   │   │   ├── tc_agents.go           # Agent API
│   │   │   ├── tc_listeners.go        # Listener API
│   │   │   └── tc_*.go                # 其他REST端点
│   │   ├── database/                  # SQLite 持久化
│   │   ├── eventing/                  # 事件Hook系统
│   │   ├── extender/                  # Go Plugin 加载器
│   │   ├── axscript/                  # JS脚本引擎 (goja)
│   │   ├── profile/                   # YAML配置解析
│   │   └── utils/
│   │       ├── krypt/                 # RC4, SHA256, MD5, CRC32
│   │       ├── token/jwt.go           # JWT HS256
│   │       ├── safe/                  # 线程安全容器
│   │       └── proxy/socks.go         # SOCKS4/5 协议
│   └── extenders/                     # 编译为 .so 的插件
│       ├── beacon_agent/              # Beacon Agent 插件
│       ├── beacon_listener_http/      # HTTP/S Listener
│       ├── beacon_listener_dns/       # DNS/DoH Listener
│       ├── beacon_listener_smb/       # SMB Listener
│       ├── beacon_listener_tcp/       # TCP Listener
│       ├── gopher_agent/              # Gopher Agent (BOF-based)
│       └── gopher_listener_tcp/       # Gopher TCP Listener
│
└── AdaptixClient/                     # C++ Qt6 客户端
    ├── CMakeLists.txt                 # C++23, Qt6, MinGW
    ├── Source/main.cpp                # 入口
    ├── Headers/
    │   ├── main.h                     # 协议常量 + 数据结构
    │   ├── MainAdaptix.h              # 根对象
    │   ├── Agent/Agent.h              # Agent 客户端模型
    │   ├── Agent/Commander.h          # 命令解析/补全
    │   ├── Client/
    │   │   ├── Requestor.h            # HTTP API 层
    │   │   ├── HttpRequestManager.h   # 异步请求队列
    │   │   ├── Storage.h              # SQLite存储
    │   │   ├── Extender.h             # 扩展管理器
    │   │   ├── AuthProfile.h          # 认证配置
    │   │   ├── TunnelEndpoint.h       # 隧道端点
    │   │   └── AxScript/*             # JS脚本引擎
    │   ├── UI/
    │   │   ├── MainUI.h               # 主窗口
    │   │   ├── Widgets/               # 14个 Dock Widget
    │   │   ├── Dialogs/               # 14个对话框
    │   │   └── Graph/                 # 会话图可视化
    │   ├── Workers/                   # 8个后台线程
    │   └── Utils/                     # 工具类
    └── Libs/
        ├── kddockwidgets/             # 高级Docking框架
        ├── Konsole/                   # 终端模拟器
        └── qlementine/                # 主题引擎
```

---

## 二、服务端核心详解

### 2.1 启动流程

`main.go` → `server.NewTeamserver()` → `ts.Start()`:

```go
func (ts *Teamserver) Start() {
    // 1. 枚举网卡
    // 2. 创建 TsConnector (gin HTTP Server)
    // 3. ts.Extender.LoadPlugins()       -- 加载所有 .yaml 插件配置
    // 4. ts.TsAxScriptLoadFromProfile()  -- 加载 AxScript
    // 5. go ts.AdaptixServer.Start()     -- 启动 HTTPS
    // 6. ts.RestoreData()                -- 从 SQLite 恢复状态
    // 7. go ts.TsAgentTickUpdate()       -- Agent tick 轮询 (800ms)
    // 8. <-stopped                       -- 阻塞等待
}
```

### 2.2 Teamserver 核心结构

```go
type Teamserver struct {
    Profile       *profile.AdaptixProfile
    DBMS          *database.DBMS
    AdaptixServer *connector.TsConnector
    Extender      *extender.AdaptixExtender

    TaskManager   *TaskManager       // 3种Handler: Task / Job / Tunnel
    Broker        *MessageBroker     // WebSocket 消息广播 (fan-out)
    TunnelManager *TunnelManager     // SOCKS/端口转发管理
    EventManager  *eventing.EventManager
    ScriptManager *axscript.ScriptManager

    Agents         safe.Map         // agentId → *Agent
    listeners      safe.Map         // listenerName → ListenerData
    wm_agent_types map[string]string  // CRC32(watermark) → agentName
    wm_listeners   map[string][]string // watermark → [name, type]
}
```

### 2.3 Agent 结构体

```go
type Agent struct {
    mu       sync.RWMutex
    data     adaptix.AgentData        // 包含 Id, Crc, Name, SessionKey,
                                       // Listener, Sleep, Jitter, Pid,
                                       // Os, Domain, Computer, Username,
                                       // WorkingTime, KillDate, Mark 等
    Extender adaptix.ExtenderAgent    // 插件提供的加解密/打包接口
    Tick     bool
    Active   bool

    HostedTasks       *safe.Queue     // 待发送给Agent的任务
    HostedTunnelTasks *safe.Queue     // 待发送的隧道任务
    HostedTunnelData  *safe.Queue     // 待发送的隧道数据

    RunningTasks safe.Map             // taskId → TaskData
    RunningJobs  safe.Map             // taskId → HookJob列表
    PivotParent  *adaptix.PivotData
    PivotChilds  *safe.Slice
}
```

### 2.4 Agent 生命周期

```
1. Listener 收到连接 → TsListenerInteralHandler(watermark, data)
2. watermark CRC32 查表 → 路由到对应 agent_type
3. TsAgentCreate() → Extender 解码"beat" → 创建 Agent → 存DB → EventAgentNew
4. TsAgentProcessData() → Extender 解密 → 更新主机信息 + 任务结果
5. TsAgentGetHostedAll() → 从队列拉任务 → PackData() → 加密返回
6. TsAgentSetTick() → 更新 LastTick → Tick=true (异步agent)
7. TsAgentTickUpdate() → 后台goroutine 800ms收集tick → 批量推客户端
```

### 2.5 API 路由体系

所有路由前缀使用 profile 配置的 `endpoint`：

```
公开 (无认证):
  POST /<endpoint>/login          → JWT access_token + refresh_token

OTP验证:
  GET  /<endpoint>/connect        → WebSocket 升级 (主通道)
  GET  /<endpoint>/channel        → WebSocket 升级 (tunnel/terminal/build)

JWT认证 (Bearer):
  POST /<endpoint>/sync           → 触发客户端同步
  POST /<endpoint>/subscribe      → 订阅同步类别
  GET  /<endpoint>/agent/list     → Agent 列表
  POST /<endpoint>/agent/generate → 构建Agent
  POST /<endpoint>/listener/create|start|stop|pause
  ... 共40+ REST端点
```

### 2.6 WebSocket 同步系统

客户端连接后订阅16类同步数据：
```
extenders, scripts, listeners, agents, agents_only_active, agents_inactive,
pivots, tasks_history, tasks_manager, tasks_only_jobs, console_history,
chat_history, chat_realtime, downloads_history, downloads_realtime,
screenshot_history, screenshot_realtime, credentials_history,
credentials_realtime, targets_history, targets_realtime, notifications, tunnels
```

同步流程：
```
1. Server → TYPE_SYNC_START { count, interfaces }
2. Server → TYPE_SYNC_BATCH { packets: [...] }
3. Server → TYPE_SYNC_FINISH
4. Client 解码 packets → 分发到各 Dock Widget
```

### 2.7 加密体系

| 组件 | 算法 | 位置 | 用途 |
|------|------|------|------|
| Agent流量 | RC4 (crypto/rc4) | `utils/krypt/crypt.go` + Agent端 `Crypt.cpp` | 心跳/任务数据加解密 |
| 密码存储 | SHA256 | `utils/krypt/hash.go` | 服务端密码哈希 |
| 认证 | JWT HS256 | `utils/token/jwt.go` | 随机32B密钥签名 |
| OTP | Time-based | `utils/token/otp.go` | WebSocket升级认证 |
| TLS | RSA 2048 / ECDHE | `pl_transport.go:440` | Listener HTTPS |

### 2.8 数据库表 (SQLite WAL模式)

| 表名 | 用途 |
|------|------|
| Listeners | Listener名称/配置/状态/Watermark |
| Agents | Id/Crc/SessionKey/Listener/Sleep/OS/Domain/Username... |
| Tasks | TaskId/AgentId/CommandLine/Message/Completed |
| Consoles | AgentId + JSON控制台输出包 |
| Downloads | FileId/路径/大小/状态(Running/Finished/Canceled) |
| Screenshots | ScreenId/路径/日期/备注 |
| Credentials | CredId/Username/Password/Realm/Type/Tag |
| Targets | TargetId/Computer/Domain/Address/OS/Tag |
| Pivots | PivotId/ParentAgentId/ChildAgentId |
| Chat | Username/Message/Date |
| ExtenderData | ExtenderName/Key/Value (插件KV存储) |

### 2.9 Extender 插件体系

插件通过 Go 原生 `plugin.Open()` 加载 `.so`:

```yaml
# config.yaml 示例 (beacon_agent)
extender_type: "agent"
extender_file: "agent_beacon.so"
ax_file: "ax_config.axs"
agent_name: "beacon"
agent_watermark: "be4c0149"
listeners:
  - "BeaconHTTP"
  - "BeaconTCP"
  - "BeaconSMB"
  - "BeaconDNS"
```

插件接口 (定义于 `github.com/Adaptix-Framework/axc2`):

```
PluginAgent:
  - GenerateProfiles(config) → agentProfiles
  - BuildPayload(config, profiles) → fileContent, filename
  - CreateAgent(beat) → AgentData, ExtenderAgent

ExtenderAgent (per-agent):
  - CreateCommand(agent, args) → TaskData, ConsoleMessage
  - Decrypt(packedData, sessionKey) → plainData
  - Encrypt(plainData, sessionKey) → packedData
  - ProcessData(agent, decryptedData) → error
  - PackTasks(agent, tasks) → packedData
  - TunnelCallbacks() / TerminalCallbacks()

PluginListener:
  - Create(name, config, customData) → ExtenderListener, ListenerData

ExtenderListener:
  - Start() / Stop() / Edit(config) / GetProfile()
  - InternalHandler(data) → agentId
```

---

## 三、客户端核心详解

### 3.1 启动流程

```
main.cpp → GlobalClient = new MainAdaptix()
  → Storage/Settings 初始化
  → Start() 登录循环:
       Login() → DialogConnect → HttpReqLogin()
       → 创建 QThread + WebSocketWorker
       → 等待 WebSocket 连接 (5秒超时)
       → mainUI->AddNewProject()
       → QApplication::exec()
```

### 3.2 关键数据结构 (main.h)

```cpp
struct AgentData {
    QString Id, Name, Listener;   bool Async;
    QString ExternalIP, InternalIP;
    int     GmtOffset, ACP, OemCP;
    uint    KillDate, WorkingTime;
    int     Sleep, Jitter;
    QString Pid, Tid, Arch;       bool Elevated;
    QString Process;
    int     Os;                   QString OsDesc;
    QString Domain, Computer, Username, Impersonated;
    QString Tags, Mark, Color;
    int     LastTick;             qint64 DateTimestamp;
};

struct TaskData {
    QString TaskId, AgentId, Type;      // TASK / JOB / TUNNEL
    QString Client, User, Computer;
    qint64  StartDate, FinishDate;
    QString CommandLine, MessageType, Message, ClearText;
    bool    Completed;
};

struct ListenerData { QString Name, Protocol, BindHost, BindPort, Status, Data; };
struct DownloadData { QString FileId, AgentId, Filename; qint64 TotalSize, RecvSize; int State; };
struct CredentialData { QString CredId, Username, Password, Realm, Type, Tag, Storage, AgentId, Host; };
struct TargetData { QString TargetId, Computer, Domain, Address; int Os; QString OsDesk, Tag, Info; bool Alive; };
struct TunnelData { QString TunnelId, AgentId, Type, Interface, Port, Client, Fhost, Fport; };
```

### 3.3 AdaptixWidget — 中央控制器

每个项目一个实例，持有所有运行时数据：

```cpp
class AdaptixWidget {
    AuthProfile* profile;
    WebSocketWorker* wsChannel;

    QMap<QString, Agent*>            AgentsMap;      // 读写锁保护
    QMap<QString, TaskData>          TasksMap;
    QVector<CredentialData>          Credentials;
    QVector<TargetData>              Targets;
    QVector<ListenerData>            Listeners;
    QVector<TunnelData>              Tunnels;
    QMap<QString, DownloadData>      Downloads;
    QMap<QString, ScreenData>        Screenshots;
    QMap<QString, PivotData>         Pivots;

    // 所有 Dock Widget
    SessionsTableWidget*   sessionsDock;
    SessionsGraph*         graphDock;
    ConsoleWidget*         consoleDock;
    ListenersWidget*       listenersDock;
    TasksWidget*           tasksDock;
    DownloadsWidget*       downloadsDock;
    // ...
};
```

### 3.4 Commander — 命令解析引擎

```cpp
class Commander : public QObject {
    // ProcessInput(agentId, cmdline) → CommanderResult
    // CommanderResult { error, message, data, is_pre_hook, post_hook, handler }
    // 命令由服务端 AxScript 定义，sync时注册到客户端
};
```

流程：
1. 用户在 Console 输入命令 → `Commander::ProcessInput()`
2. 解析命令行 → 匹配已注册命令 → 填充参数
3. 执行 pre-hook (可中断或改写)  → 返回 CommanderResult
4. ConsoleWidget 处理结果 → 分派到 HTTP API 或 Alias

### 3.5 AxScript 引擎体系

基于 Qt `QJSEngine`，提供 JS ↔ C++ 双向通信：

```
AxScriptManager (总管)
  ├── mainScript           # 主 REPL 引擎
  ├── scripts{}            # 客户端扩展脚本
  ├── server_scripts{}     # 服务端同步的脚本
  └── config_scripts{}     # Listener/Agent/Service 配置脚本

BridgeApp (app.*)          # 50+ API方法
  - app.agents() / app.execute_command()
  - app.encode_data() / app.hash()
  - app.bof_pack() / app.file_read()
  - app.open_agent_console/files/terminal()

BridgeEvent (event.*)      # 事件订阅
  - event.on_new_agent() / event.on_interval()
  - event.on_filebrowser_disks/list/upload()

BridgeForm (form.*)        # 动态UI
  - form.create_label/combo/spin/table/tabs/groupbox()
  - form.create_dialog()

BridgeMenu (menu.*)        # 上下文菜单
  - menu.add_session_main/agent/browser()
  - menu.add_filebrowser/downloads/tasks()
```

### 3.6 协议消息类型 (main.h)

```cpp
TYPE_SYNC_START  (0x11)  TYPE_SYNC_FINISH  (0x12)
SP_TYPE_EVENT    (0x13)  TYPE_SYNC_BATCH   (0x14)
TYPE_CHAT_MESSAGE(0x18)  TYPE_SERVICE_DATA (0x19)
TYPE_REG_LISTENER(0x21)  TYPE_REG_AGENT    (0x22)
TYPE_LISTENER_START(0x31)  TYPE_AGENT_NEW  (0x41)
TYPE_AGENT_TICK  (0x44)  TYPE_AGENT_TASK_SYNC (0x49)
TYPE_DOWNLOAD_CREATE(0x51)  TYPE_TUNNEL_CREATE(0x57)
TYPE_BROWSER_DISKS(0x61)  TYPE_AGENT_CONSOLE_OUT(0x69)
TYPE_PIVOT_CREATE(0x71)  TYPE_CREDS_CREATE(0x81)
TYPE_AXSCRIPT_COMMANDS(0x91)
```

### 3.7 Worker 线程

| Worker | 基类 | 功能 |
|--------|------|------|
| WebSocketWorker | QThread | 主WebSocket通道，15s心跳ping |
| LastTickWorker | QThread | 周期性更新Agent心跳时间 |
| BuildWorker | QObject | 通过WebSocket构建Agent二进制 |
| DownloaderWorker | QObject | HTTP文件下载 (带进度) |
| UploaderWorker | QObject | HTTP文件上传 |
| TunnelWorker | QObject | TCP↔WebSocket隧道转发 |
| SocksHandshakeWorker | QObject | SOCKS4/5握手协议 |
| TerminalWorker | QObject | 远程终端I/O中继 |
| AxScriptWorker | QThread | 后台JS脚本执行 |

---

## 四、Beacon Agent 通信协议深度剖析

### 4.1 心跳包格式 (HTTP Listener)

**请求**:
```
POST /<uri> HTTP/1.1
Host: <callback_address>
User-Agent: <user_agent>
<parameter_name>: base64( RC4(encrypt_key, CRC32(watermark)[4B] + AgentID[4B] + agentInfo) )
Content-Type: ... (来自 request_headers)

<body = 加密的任务结果数据 (RC4(encrypt_key, packerData)) >
```

**服务端响应**:
```
HTTP/1.1 200 OK
<server_headers>

<page-payload模板，<<<PAYLOAD_DATA>>> 替换为 base64( RC4(encrypt_key, 待执行任务数据) ) >
```

### 4.2 心跳解析流程 (`pl_transport.go:393`)

```go
func (t *TransportHTTP) parseBeatAndData(ctx *gin.Context) {
    // 1. 从 Header 取 <parameter_name> 的值
    beat = ctx.Request.Header.Get(t.Config.ParameterName)

    // 2. Base64 解码
    agentInfoCrypt = base64.StdEncoding.DecodeString(beat)

    // 3. RC4 解密 (密钥 = EncryptKey, 32hex → 16bytes)
    rc4crypt.XORKeyStream(agentInfo, agentInfoCrypt)

    // 4. 提取 agentType (前4字节) + agentId (后续4字节)
    agentType = binary.BigEndian.Uint32(agentInfo[:4])    // CRC32(watermark)
    agentId   = binary.BigEndian.Uint32(agentInfo[4:8])

    // 5. 剩余 agentInfo 包含主机信息 (AgentInfo 序列化)
    // 6. 读取 Body → 加密的任务数据 → TsAgentProcessData()
}
```

### 4.3 URI/UA/HostHeader 验证链 (`pl_transport.go:293`)

```go
func (t *TransportHTTP) processRequest(ctx *gin.Context) {
    // 1. URI 验证 — 必须匹配配置的 URI 列表
    // 2. HostHeader 验证 — 如果配置了, 必须匹配
    // 3. UserAgent 验证 — 必须匹配配置的 UA 列表
    // 4. 任一验证失败 → pageError() → 返回自定义404页面
}
```

### 4.4 Agent 端加密实现 (`src_beacon/beacon/Crypt.cpp`)

```cpp
void EncryptRC4(unsigned char* data, int dataLength,
                unsigned char* key, int keyLength) {
    unsigned char S[256];
    RC4Init(key, S, keyLength);           // KSA 密钥调度
    RC4EncryptDecrypt(data, dataLength, S); // PRGA + XOR
}
// 解密 = 加密 (RC4 对称)
```

### 4.5 Agent 主循环 (`src_beacon/beacon/MainAgent.cpp`)

```cpp
DWORD WINAPI AgentMain(LPVOID lpParam) {
    ApiLoad();                          // 动态加载Win32 API
    g_Agent = new Agent();
    g_Connector = CreateConnector();    // HTTP/SMB/TCP/DNS

    beat = g_Agent->BuildBeat(&beatSize);
    g_Connector->SetProfile(&config.profile, beat, beatSize);

    do {
        if (!g_Connector->WaitForConnection()) continue;  // sleep + jitter

        do {
            g_Connector->Exchange(outData, outSize, SessionKey);  // 发送+接收
            g_Agent->commander->ProcessCommandTasks(recvData, recvSize, packerOut);
            g_Agent->downloader->ProcessDownloader(packerOut);
            g_Agent->jober->ProcessJobs(packerOut);
            g_Agent->proxyfire->ProcessTunnels(packerOut);
            g_Agent->pivotter->ProcessPivots(packerOut);
            g_AsyncBofManager->ProcessAsyncBofs(packerOut);

            g_Connector->Sleep(wakeupEvent, workingSleep, sleepDelay, jitterDelay, hasOutput);
        } while (g_Connector->IsConnected() && g_Agent->IsActive());

        g_Connector->Disconnect();
    } while (g_Agent->IsActive());
}
```

### 4.6 Agent 构建流程

```
TsAgentGenerate()
  → AgentBuilder (WebSocket channel)
    → Extender.BuildPayload(config, profiles)
      → 读取 src_beacon/files/config.tpl
      → 填充 PROFILE / PROFILE_SIZE 宏
      → 选择格式: Exe / Service Exe / DLL / Shellcode
      → Shellcode格式: 拼接 stub.x64.bin + 配置块
      → 编译 → 返回二进制
```

---

## 五、特征修改关键源码定位

这里从源码层面精准定位所有特征修改点：

### 5.1 Listener HTTP 配置文件

**文件**: `AdaptixServer/extenders/beacon_listener_http/ax_config.axs`

| 行号 | 默认值 | 说明 | C2IntelFeeds 指纹风险 |
|------|--------|------|----------------------|
| L30 | `["/api/v1/status", "/updates/check.php", "/content.html"]` | URI路径列表 | **高** — 已被收录到 C2IntelFeeds |
| L35 | `"Mozilla/5.0 (Windows NT 6.2; rv:20.0) Gecko/20121202 Firefox/20.0"` | User-Agent | **高** — 特征明显 |
| L38 | `"X-Beacon-Id"` | 心跳参数名 | **高** |
| L42 | `ax.random_string(32, "hex")` | 加密密钥(32hex) | 低 — 随机生成，但可在测绘中关联 |
| L111 | `<title>ERROR 404 - Nothing Found</title>` | 404页面HTML | **高** — 默认模板指纹 |
| L120 | `{"status": "ok", "data": "<<<PAYLOAD_DATA>>>", "metrics": "sync"}` | 响应数据模板 | **高** — JSON结构指纹 |

### 5.2 Agent 配置文件

**文件**: `AdaptixServer/extenders/beacon_agent/config.yaml`

```yaml
agent_name: "beacon"
agent_watermark: "be4c0149"     # ← 需修改，CRC32后嵌入心跳前4字节
```

**文件**: `AdaptixServer/extenders/beacon_agent/ax_config.axs`

定义了所有 beacon 命令 (cat, cd, cp, download, execute bof, getuid, jobs, link, ls, mkdir, mv, ps, pwd, rev2self, rm, socks, sleep, terminate, upload, shell, powershell, interact 等)。

### 5.3 服务端 Profile 配置

**文件**: `AdaptixServer/core/profile/profile.go`

```go
type TsProfile struct {
    Interface      string            `yaml:"interface"`    // 监听接口
    Port           int               `yaml:"port"`         // 监听端口
    Endpoint       string            `yaml:"endpoint"`     // ← 需修改，URI前缀
    Password       string            `yaml:"password"`
    OnlyPassword   bool              `yaml:"only_password"`
    Operators      map[string]string `yaml:"operators"`
    Cert           string            `yaml:"cert"`
    Key            string            `yaml:"key"`
    Extenders      []string          `yaml:"extenders"`
}
```

**HTTP Server 配置**: `TsHttpServer` 包含 TLS 版本、密码套件、超时、404页面路径、自定义 Header 等。

### 5.4 HTTPS Listener 传输层

**文件**: `AdaptixServer/extenders/beacon_listener_http/pl_transport.go`

关键函数:
- `generateSelfSignedCert()` (L440) — 自签名证书生成，Subject 无组织信息
- `pageError()` (L512) — 返回自定义404页面，可模拟任何Web服务
- `processRequest()` (L293) — URI/UA/HostHeader 验证

### 5.5 Agent 端通信模块

**文件**: `AdaptixServer/extenders/beacon_agent/src_beacon/beacon/ConnectorHTTP.cpp`

- API 动态解析: 使用 `GetSymbolAddress` + hash 而非直接 `GetProcAddress`
- 字符串隐藏: `HdChrA('w')` 逐字符构造库名
- WinInet: 每次请求重建句柄以轮换UA

### 5.6 Agent Loader / Shellcode Stub

**文件**: `AdaptixServer/extenders/beacon_agent/src_beacon/files/stub.x64.bin`
**文件**: `AdaptixServer/extenders/beacon_agent/src_beacon/files/stub.x86.bin`

这两个是编译好的二进制 stub 文件，作为 Shellcode 格式的基础。编译时与新配置拼接：
```
[stub.bin] + [RC4加密的配置块(含PROFILE)]
```

Loader 层特征命中点高度集中：
- shellcode 解码 → 内存分配 → 跳转执行
- call/jmp 模式高度稳定
- 编译器优化后字节序列极易固化

对 `5F 00 00 E8` → `5F 90 90 E8` 的 patch 即修改 stub 中的 call 指令序列，断开 AV 特征 hash。

---

## 六、免杀架构分析

### 6.1 静态免杀

| 技术 | 实现位置 | 机制 |
|------|---------|------|
| IAT Hiding | `config.tpl` + `ApiLoader.cpp` | 空导入表，所有 API 通过 hash 动态解析 |
| 字符串混淆 | `ConnectorHTTP.cpp`, `ApiDefines.h` | `HdChrA('w')` 逐字符构造，编译时展开 |
| 自定义内存分配 | `MemorySaver.cpp` | 本地分配器，避免 HeapAlloc 检测 |
| RC4 加密配置 | `AgentConfig.h` → `BuildBeat()` | 配置块 RC4 加密存储在二进制中 |
| 分段编译 | `main.cpp` `#if defined(BUILD_*)` | Exe/ServiceExe/DLL/Shellcode 条件编译 |

### 6.2 动态免杀

| 技术 | 实现位置 | 机制 |
|------|---------|------|
| WinInet API | `ConnectorHTTP.cpp:76-88` | 非 WinHTTP，无 ETW 日志 |
| 连接重建 | `ConnectorHTTP.cpp:198-200` | 每次请求关闭旧句柄刷新UA |
| Sleep + Jitter | `main.h` → `WaitMask.cpp` | 可配置的睡眠抖动 |
| WorkingTime / KillDate | `AgentConfig.h` | 按时间段活跃，到期自毁 |
| Sideloading | `pl_sideloading.go` | DLL 劫持支持 |
| BOF 执行 | `bof_loader.cpp`, `Boffer.cpp` | 内存加载不落地 |
| 进程注入 (BOF) | Extension-Kit 的 Injection-BOF | 通过 BOF 执行 shellcode 注入 |

### 6.3 流量伪装

| 技术 | 配置位置 | 机制 |
|------|---------|------|
| 多URI轮询 | `ax_config.axs` URI列表 | 每次请求随机选择 |
| 多UA轮询 | `ax_config.axs` UA列表 | 每次请求随机选择 |
| 多HostHeader | `ax_config.axs` HostHeader列表 | 模拟多个虚拟主机 |
| 多回调地址 | `ax_config.axs` Callback列表 | 多域名/IP故障转移 |
| 自定义404 | `ax_config.axs` textError | 未授权访问返回伪装页面 |
| 自定义响应模板 | `ax_config.axs` textPayload | 数据包裹在正常JSON/HTML中 |
| 自定义Server Header | `ax_config.axs` server_headers | 伪装 nginx/apache |
| RC4加密 | `Crypt.cpp` + `pl_transport.go` | 流量不可直接识别 |

---

## 七、BOF 执行机制

### 7.1 BOF 加载器

**文件**: `src_beacon/beacon/bof_loader.cpp` + `Boffer.cpp`

```
用户: execute-assembly /PrintNotifyPotato.exe whoami
  → Commander 解析 → create_command("bof") → PostHook
  → 服务端 TaskManager → 分发到 Agent
  → Agent ProcessCommandTasks() → BOF Loader
  → bof_loader.cpp: 解析 COFF → 重定位 → 解析符号 → 调用 go()
  → 输出回传
```

### 7.2 异步 BOF

`Boffer.cpp: Initialize()` → 创建独立线程池 → AsyncBofManager
- 不阻塞主心跳循环
- 支持长时间运行的 BOF（如键盘记录、屏幕监控）

---

## 八、数据流完整路径

### 8.1 命令下发

```
操作员 Console 输入 → Commander::ProcessInput()
  → AxScript pre_hook (可拦截/改写)
  → HTTP POST /agent/command/execute → JWT认证
  → connector/tc_agents.go → server/ts_agent.go
  → TsAgentCommand() → 创建 TaskData → 入 HostedTasks 队列
  → Agent 下次心跳 → TsAgentGetHostedAll() → PackData() → RC4加密
  → 返回加密blob → page-payload 模板替换 → 响应
  → Agent Connector::Exchange() 接收 → RC4解密
  → Commander::ProcessCommandTasks() → 执行
  → 结果写入 Packer → 下次心跳上传
```

### 8.2 隧道数据

```
外部客户端 → SOCKS端口 → soskHandshakeWorker
  → TunnelWorker (TCP↔WebSocket)
  → 服务端 TunnelManager → HostedTunnelData 队列
  → Agent 心跳时获取 → Proxyfire 处理 → 目标连接
  → 响应反向路径回传
```

---

## 九、与 Cobalt Strike 对比

| 维度 | Cobalt Strike | AdaptixC2 |
|------|--------------|-----------|
| 服务端语言 | Java (闭源) | Go (开源) |
| 客户端 | Java Swing / 自绘 | C++ Qt (原生跨平台) |
| 插件系统 | Aggressor Script (Sleep) | AxScript (JavaScript) + Go Plugin |
| Agent | Windows Beacon (闭源) | C++ Beacon (开源于 extender) |
| BOF | 原生支持 | 原生支持 (bof_loader.cpp) |
| 多用户 | 支持 | 支持 (JWT + OTP) |
| 隧道 | SOCKS/端口转发 | SOCKS4/5 + 本地/远程端口转发 |
| 免杀 | 需要外部工具 | IAT Hiding / RC4 / 动态API解析 内置 |
| 通信协议 | HTTP/HTTPS/DNS/SMB/TCP | HTTP/HTTPS/DNS/DoH/SMB/TCP + Gopher(mTLS) |
| P2P | Pivot (TCP/SMB) | Pivot (TCP/SMB) + Session Graph |
| 扩展性 | Aggressor Script | AxScript + Go Plugin + AxScript UI |

---

## 十、关键文件索引

### 服务端核心
- `AdaptixServer/main.go` — 入口
- `AdaptixServer/core/server/server.go` — 启动流程
- `AdaptixServer/core/server/utils.go` — 核心数据结构
- `AdaptixServer/core/server/ts_agent.go` — Agent 生命周期管理
- `AdaptixServer/core/server/ts_sync.go` — 客户端同步
- `AdaptixServer/core/connector/connector.go` — HTTP/WS API层
- `AdaptixServer/core/database/database.go` — SQLite持久化
- `AdaptixServer/core/eventing/evt_manager.go` — 事件Hook
- `AdaptixServer/core/extender/extender.go` — Go Plugin加载
- `AdaptixServer/core/profile/profile.go` — Profile配置解析
- `AdaptixServer/core/utils/krypt/crypt.go` — RC4/SHA256加密

### Extender 插件
- `AdaptixServer/extenders/beacon_listener_http/pl_transport.go` — HTTP Listener核心
- `AdaptixServer/extenders/beacon_listener_http/pl_main.go` — Listener插件入口
- `AdaptixServer/extenders/beacon_listener_http/ax_config.axs` — Listener UI + 默认配置 (**特征修改核心文件**)
- `AdaptixServer/extenders/beacon_agent/pl_main.go` — Agent插件入口
- `AdaptixServer/extenders/beacon_agent/pl_packer.go` — 数据打包/解包
- `AdaptixServer/extenders/beacon_agent/ax_config.axs` — Agent UI + 命令定义
- `AdaptixServer/extenders/beacon_agent/config.yaml` — Agent watermark配置

### Agent 源码 (C++)
- `extenders/beacon_agent/src_beacon/beacon/main.cpp` — Agent入口 (4模式)
- `extenders/beacon_agent/src_beacon/beacon/MainAgent.cpp` — Agent主循环
- `extenders/beacon_agent/src_beacon/beacon/ConnectorHTTP.cpp` — HTTP通信模块
- `extenders/beacon_agent/src_beacon/beacon/ConnectorDNS.cpp` — DNS通信模块
- `extenders/beacon_agent/src_beacon/beacon/Crypt.cpp` — RC4加密
- `extenders/beacon_agent/src_beacon/beacon/ApiLoader.cpp` — 动态API解析
- `extenders/beacon_agent/src_beacon/beacon/bof_loader.cpp` — BOF加载器
- `extenders/beacon_agent/src_beacon/beacon/Boffer.cpp` — 异步BOF管理
- `extenders/beacon_agent/src_beacon/beacon/MemorySaver.cpp` — 本地内存分配器
- `extenders/beacon_agent/src_beacon/beacon/Packer.cpp` — 二进制打包
- `extenders/beacon_agent/src_beacon/files/config.tpl` — 配置模板
- `extenders/beacon_agent/src_beacon/files/stub.x64.bin` — x64 Shellcode Stub
- `extenders/beacon_agent/src_beacon/files/stub.x86.bin` — x86 Shellcode Stub

### 客户端核心
- `AdaptixClient/Source/main.cpp` — 入口
- `AdaptixClient/Headers/MainAdaptix.h` — 根对象
- `AdaptixClient/Headers/UI/MainUI.h` — 主窗口
- `AdaptixClient/Headers/UI/Widgets/AdaptixWidget.h` — 项目中央控制器
- `AdaptixClient/Headers/UI/Widgets/ConsoleWidget.h` — Agent控制台
- `AdaptixClient/Headers/UI/Widgets/SessionsTableWidget.h` — Sessions表
- `AdaptixClient/Headers/Agent/Commander.h` — 命令解析引擎
- `AdaptixClient/Headers/Workers/WebSocketWorker.h` — WebSocket线程
- `AdaptixClient/Headers/Client/Requestor.h` — HTTP API层
- `AdaptixClient/Headers/Client/AxScript/AxScriptEngine.h` — JS脚本引擎
- `AdaptixClient/Headers/Client/AxScript/BridgeApp.h` — JS Bridge (app.*)
- `AdaptixClient/Headers/Client/AxScript/BridgeEvent.h` — JS Bridge (event.*)
- `AdaptixClient/Headers/Client/AxScript/BridgeForm.h` — JS Bridge (form.*)
- `AdaptixClient/Headers/Client/AxScript/BridgeMenu.h` — JS Bridge (menu.*)

---

## 十一、先知社区4篇文章 vs v1.2 源码对比分析

> 4篇文章基于 AdaptixC2 v0.8（约2024年初），当前分析版本为 v1.2（2025-2026）。
> 本章逐篇对照文章描述与当前源码，标注每一项差异点的 v1.2 实际实现。

### 11.1 文章一：Beacon HTTP 通信机制与流量解密 (idocdown:16985 / xz:18820)

**文章核心结论（v0.8）：**
- 双层RC4加密：静态 EncryptKey（外层） + SessionKey（内层）
- Beat = base64(RC4(EncryptKey, agentType[4B] + agentId[4B] + agentInfo))
- SessionKey 位于 beat 偏移量 36 字节处
- 任务下发：JSON body 中 `{"data": "Base64(RC4(SessionKey, payload))"}`
- 源码文件：`Extenders/listener_beacon_http/pl_http.go`、`pl_agent.go`

**v1.2 变化对照：**

| 文章描述 (v0.8) | v1.2 实际实现 | 变更类型 |
|---|---|---|
| 源文件 `pl_http.go` | 已重命名为 `pl_transport.go`，使用 Gin 框架 | 架构重构 |
| 双层RC4 (EncryptKey + SessionKey) | 传输层仅单层RC4，`parseBeatAndData()` 仅用 EncryptKey 解密 beat；body 也用 EncryptKey 解密 | **简化** |
| SessionKey 在beat偏移36处固定提取 | SessionKey 仍在 agentInfo 中被 `CreateAgent()` 的 Packer 解析 (`pl_main.go:793`)，但位置由 Packer 格式决定，非固定偏移 | 灵活性提升 |
| HTTP响应为 JSON 格式 | 响应嵌入 HTML 模板 `WebPageOutput`，使用 `<<<PAYLOAD_DATA>>>` 占位符替换 | **流量伪装增强** |
| 单 URI `/endpoint` | 多 URI 数组验证 (`pl_transport.go:304-319`)，支持多个合法路径 | 灵活性提升 |
| 无 Host Header 验证 | 新增 HostHeader 白名单验证 (`pl_transport.go:321-335`) | **安全增强** |
| 无 UA 验证 | 多 User-Agent 白名单验证 (`pl_transport.go:337-350`) | **安全增强** |
| Body 为 JSON `{"data": "Base64(...)"}` | Body 为原始二进制密文 `io.ReadAll(ctx.Request.Body)`，无 JSON 包装 | 简化传输 |
| `EncryptKey` 从数据库持久化 | 验证同上，但新增 `validConfig()` 强校验：必须32hex字符 (`pl_transport.go:148-151`) | 配置规范 |

**关键差异详析：**

1. **SessionKey 角色的变化**：文章描述的双层加密中，SessionKey 用于加密任务内容。v1.2 中 SessionKey 字段仍然存在于 `AgentData` 结构体中 (`agentData.SessionKey` at `pl_main.go:793`)，但它在 `CreateAgent()` 中从 beat 的 agentInfo 部分解析得到，其加解密由 `ExtenderAgent.Encrypt/Decrypt` 方法处理（`pl_main.go:806-816`）。在传输层 `pl_transport.go:374`，`TsAgentProcessData(agentId, bodyData)` 接收到的 bodyData 是原始二进制，加密解密由 Extender 层而非 Transport 层负责。

2. **响应模板化**：v0.8 任务响应为 JSON 格式，v1.2 改为 HTML 模板嵌入（`pl_transport.go:378`：`strings.ReplaceAll(t.Config.WebPageOutput, "<<<PAYLOAD_DATA>>>", string(responseData))`）。这使 C2 响应流量可以伪装为正常网页，增加检测难度。

3. **Gin 框架迁移**：从原生 `net/http` + mux 迁移到 `gin-gonic/gin` 框架，提供了中间件支持 (`pl_transport.go:167-172` ResponseHeaders)，代码结构更清晰。

### 11.2 文章二：Agent样本分析及流量特征魔改 (idocdown:16992 / xz:19028)

**文章核心结论（v0.8）：**
- Profile = `[4B profileSize (LittleEndian)] [RC4加密的配置] [16B RC4 Key]`
- 通过搜索 "Undefined symbol" 字符串定位到密钥静态特征
- 示例密钥偏移 0x124DE
- 魔改入口：`profile.json` → 端口4321 → 18080，URI `/endpoint` → `/manager/html`
- 删除 `Server: AdaptixC2` 和 `Adaptix Version: v0.8` 头
- 建议 JSON 包装 body

**v1.2 变化对照：**

| 文章描述 (v0.8) | v1.2 实际实现 | 变更类型 |
|---|---|---|
| Profile 结构 `[4B size][data][16B key]` | `PackArray([len(cryptParams), cryptParams, encryptKey])` 序列化后用 `\xNN` 格式转为C字符串，通过 `-DPROFILE='\"...\"'` 编译器宏注入 (`pl_main.go:512-521`) | **编译方式变更** |
| "Undefined symbol" 作密钥定位器 | Profile 不再用字符串存储，直接作为编译器宏定义写入 `config.cpp`，搜索 "Undefined symbol" 定位法**可能失效** | **反分析增强** |
| `profile.json` 配置 | 配置通过 `ax_config.axs` AxScript 定义UI + 默认值，JSON 在运行时生成 | 架构升级 |
| 默认端口 4321 | 端口由创建时配置，无固定默认值 | 灵活性提升 |
| 默认 URI `/endpoint` | 默认 URI 数组 `["/api/v1/status","/updates/check.php","/content.html"]` (`ax_config.axs:L30`) | 多样化和伪装 |
| `Server: AdaptixC2` 头 | Server 头完全可配置，`Server_headers` 字段自定义所有响应头 (`pl_main.go:60-76`) | **已移除硬编码** |
| JSON body 包装建议 | v1.2 已实现 HTML 模板包装方案（比 JSON 更好），Payload 嵌入在完整网页中 | **已超越建议** |
| 单 C2 地址 | 支持多 C2 地址轮换（Callback_addresses 数组），`RotationMode` sequential/random (`pl_main.go:431-434`) | **新增** |

**关键差异详析：**

1. **Profile 编译方式彻底变更**：v0.8 的 Profile 以 `[4B size][data][16B key]` 格式直接嵌入二进制，使得通过特征字节搜索密钥成为可能。v1.2 改为：
   ```go
   // pl_main.go:512-521
   profileArray := []interface{}{len(cryptParams), cryptParams, encryptKey}
   packedProfile, _ := PackArray(profileArray)
   // 转为 \xNN 字符串，通过 -DPROFILE 编译器宏注入
   profileString := ""
   for _, b := range packedProfile {
       profileString += fmt.Sprintf("\\x%02x", b)
   }
   ```
   这种方式的 Profile 以 C 字符串字面量形式编译进 `config.cpp`，与文章描述的 `[4B len][data][key]` 结构不同，直接搜索字节特征更加困难。

2. **IAT Hiding 新增**：v1.2 Generation UI 新增 `IatHiding` 复选框 (`pl_main.go:569-571`)：
   ```go
   if generateConfig.IatHiding {
       cFlags += " -DIAT_HIDING"
       lFlags += " -nostdlib -nostartfiles -nodefaultlibs"
   }
   ```
   这比文章建议的任何流量魔改都更底层——直接从编译层面消除 IAT 特征。

3. **Sideloading 原生支持**：v1.2 内置 DLL Sideloading 生成 (`pl_main.go:677-687`)，不再需要外部工具拼接。

4. **连接轮换**：`RotationMode` 支持 sequential/random 两种模式 (`pl_main.go:431-434`)，Agent 可在多个 C2 地址间切换。

### 11.3 文章三：Gopher TCP 通信机制与 mTLS 流量解密 (idocdown:17123 / xz:18802)

**文章核心结论（v0.8）：**
- mTLS 双向认证，证书（client.key, client.cert, ca.cert）嵌入 Agent
- 三层嵌套 Msgpack 结构
- AES-GCM 加密（Listener Key + Session Key）
- Agent 二进制需用 Ghidra + GolangAnalyzerExtension 分析
- 3969 字节配置块
- `InsecureSkipVerify: true` 绕过证书验证

**v1.2 变化对照：**

| 文章描述 (v0.8) | v1.2 实际实现 | 变更类型 |
|---|---|---|
| 三层 Msgpack 嵌套 | 仍用 Msgpack v5，但结构更清晰：`StartMsg{Type, Data}` → `InitPack{Id, Type, Data}` (`pl_transport.go:75-84`) | 结构优化 |
| 仅 INIT_PACK 处理 | 6种包类型：INIT_PACK(1)/EXFIL_PACK(2)/JOB_PACK(3)/TUNNEL_PACK(4)/TERMINAL_PACK(5)/BOF_PACK(6) (`pl_transport.go:66-73`) | **大幅扩展** |
| AES-GCM 加密 | 仍用 AES-GCM (`pl_transport.go:651-695`)，但 Tunnel/Terminal 使用独立的 AES-CTR 通道加密 | 加密分层 |
| 3969 字节配置块 | 配置大小可变，由 PackArray 打包后的长度决定 | 灵活性提升 |
| 证书嵌入 | 证书/密钥字段独立：CaCert、ServerCert、ServerKey、ClientCert、ClientKey (`pl_transport.go:47-51`) | 证书管理更清晰 |
| `InsecureSkipVerify: true` | v1.2 Server 端使用 `tls.RequireAndVerifyClientCert` (`pl_transport.go:193`) 强制验证客户端证书 | **安全增强** |
| Ghidra 分析 | Agent 侧仍为 Go 编译二进制，但新增 `TcpBanner` 配置项 (`pl_transport.go:234-236`)，可设随机欢迎信息增加混淆 | **新增** |
| 无超时控制 | 新增 `Timeout` 配置和 `SetReadDeadline` 5秒超时 (`pl_transport.go:243`) | **新增** |

**关键差异详析：**

1. **包类型扩展**：v0.8 仅处理 INIT_PACK，v1.2 处理 6 种包类型，每种有独立的 Msgpack 结构体（`pl_transport.go:80-115`）。Tunnel/Terminal 类型使用独立的 AES-CTR 密钥（per-connection random Key+IV），与主通信的 AES-GCM 分离。

2. **连接管理模型变更**：
   - v0.8 为同步请求-响应模型
   - v1.2 Agent 连接保持长连接，`AgentConnects` map 管理所有活跃连接 (`pl_transport.go:291`)，使用 `isClientConnected()` 心跳检测

3. **TcpBanner 混淆**：新增在连接建立后发送自定义 Banner (`pl_transport.go:234-236`)，可伪装为任意 TCP 服务。

4. **Tunnel/Terminal 独立加密通道**：
   ```go
   // pl_transport.go:415-421
   blockEnc, _ := aes.NewCipher(tunPack.Key)
   encStream := cipher.NewCTR(blockEnc, tunPack.Iv)
   encWriter := &cipher.StreamWriter{S: encStream, W: conn}
   ```
   每个 Tunnel/Terminal 连接使用独立的 AES-CTR 流加密，与主通信加密密钥分离。

### 11.4 文章四：武器化二次开发 (idocdown:17152 / xz:19007)

**文章核心结论（v0.8）：**
- Qt LinguistTools 中文化
- C# Loader (Assembly.Load 内存加载) + C++ DLL + Shellcode 三阶段
- WMI 事件订阅持久化
- 进程注入 (Section Injection / Process Hollowing)
- 反虚拟机/反调试/反沙箱
- Go 编译环境问题 (网络/依赖)

**v1.2 变化对照：**

| 文章描述 (v0.8) | v1.2 实际实现 | 变更类型 |
|---|---|---|
| Qt Linguist 中文化 | Qt6 版本仍适用，步骤基本相同 | 兼容 |
| C# Loader + C++ DLL + Shellcode | AdaptixC2 自身不含 C# Loader，但 v1.2 新增 IAT Hiding、Sideloading、多格式输出 (Exe/SvcExe/DLL/Shellcode) | **原生能力增强** |
| 外部进程注入 | BOF 执行器仍为内置 (`bof_loader.cpp`)，Shellcode 生成现编 stub + DLL 拼接 (`pl_main.go:727-735`) | 架构优化 |
| WMI 持久化 | v1.2 Agent 支持 Service Exe 格式 (`BUILD_SVC`)，原生 Windows 服务持久化 | **原生支持** |
| 反分析技术 | IAT Hiding 消除导入表特征，`-fno-ident -fno-stack-protector` 编译选项 (`pl_main.go:301`) | **编译级反分析** |
| Go 编译 Agent | 已迁移到 MinGW 交叉编译 C++ 源码，Go 仅用于 Server | 无变化 |

**关键差异详析：**

1. **原生 Sideloading 替换外部 DLL 劫持**：v1.2 GenerateConfig 直接支持 DLL Sideloading (`pl_main.go:677-687`)：
   ```go
   if generateConfig.IsSideloading {
       defPath, err := CreateDefinitionFile(sideloadingContent, tempDir)
       lFlags += " " + defPath
   }
   ```
   通过解析原始 DLL 导出表生成 `.def` 文件，编译时自动生成兼容的劫持 DLL，无需外部工具。

2. **IAT Hiding 作为原生功能**：v1.2 将 IAT Hiding 作为 GenerateUI 中的复选框选项，编译时注入 `-DIAT_HIDING` 预处理宏，使用自定义 `crt.cpp` 替代标准 CRT。这是文章描述的"三阶段加载"的编译时替代方案。

3. **Shellcode Stub 架构**：v1.2 的 Shellcode 生成方式为 Stub + DLL 拼接 (`pl_main.go:727-735`)：
   ```go
   if generateConfig.Format == "Shellcode" {
       stubContent, _ := os.ReadFile(stubPath)  // stub.x64.bin 或 stub.x86.bin
       Payload = append(stubContent, buildContent...)
   }
   ```
   Stub 代码负责在内存中加载 DLL，与文章的自定义 C# Loader 功能等价但更轻量。

### 11.5 综合差异总结

| 维度 | v0.8 (文章时代) | v1.2 (当前) |
|---|---|---|
| **传输层框架** | 原生 net/http | Gin 框架 |
| **加密层数** | 双层RC4 | 传输层单层ChaCha20，SessionKey 由Extender管理 |
| **响应格式** | JSON | HTML 模板嵌入 |
| **URI 验证** | 单一路径 | 多URI白名单 + HostHeader + UA 三重验证 |
| **Profile 编译** | 二进制直接嵌入 | 编译器宏 -DPROFILE |
| **IAT Hiding** | 无 | 原生内置 (`-DIAT_HIDING`) |
| **Sideloading** | 需外部工具 | 原生支持 .def 自动生成 |
| **连接轮换** | 单C2 | 多C2地址 sequential/random 轮换 |
| **Gopher 包类型** | 1种 (INIT) | 6种 (INIT/EXFIL/JOB/TUNNEL/TERMINAL/BOF) |
| **Tunnel 加密** | 单一AES-GCM | AES-GCM(主通信) + AES-CTR(Tunnel/Terminal独立通道) |
| **Agent 格式** | Exe/DLL | Exe/ServiceExe/DLL/Shellcode |
| **Build 安全** | 基础 | IAT Hiding + -nostdlib + 自定义crt |
| **配置文件** | profile.json | ax_config.axs (AxScript) + config.yaml |
| **硬编码特征** | "Server: AdaptixC2" 等 | 全部可配置 |

### 11.6 已被修复/变更的文章所述"弱点"

1. **"Server: AdaptixC2" 响应头** → v1.2 已移除，改用可配置的 `ResponseHeaders`
2. **单 `/endpoint` URI** → v1.2 改为多 URI 数组，默认 3 个伪装路径
3. **Profile 静态特征明显** → v1.2 编译方式从字符串嵌入改为编译器宏注入
4. **双层RC4可被解密** → 已修复：传输层加密已从 RC4 迁移为 ChaCha20 (RFC 8439)，32 字节密钥 + 12 字节随机 Nonce，消除 RC4 已知弱点 (FMS/Bias 攻击)
5. **JSON 响应特征** → v1.2 响应嵌入HTML模板，比JSON更难指纹识别
6. **mTLS InsecureSkipVerify** → v1.2 Server强制 `RequireAndVerifyClientCert`

### 11.7 仍未变更/仍存在的风险

1. **Beat 格式结构** — 核心 Beat 语义 (agentType + agentId + agentInfo) 保持不变，但加密层已从 RC4 替换为 ChaCha20，Outside 层增加了 12 字节随机 Nonce
2. **WinInet API** — HTTP Agent 仍使用 WinInet API，其连接行为可被 EDR 监控
3. **Shellcode 体积** — Stub + DLL 拼接方式可能导致 Shellcode 体积较大
4. **C2Intelfeeds 指纹收录** — 默认 URI/UA/Header 名已被威胁情报收录，部署前必须修改
5. **Go Plugin 加载** — `.so` 文件分发可能被安全软件检测

---

## 十二、定制修改记录 — Modification #1: RC4 → ChaCha20

> 修改日期: 2026-05-19
> 影响范围: Agent (C++) + Server (Go) 全部传输层加密
> 修改策略: 密钥/Nonce/分组密码实现与 RFC 8439 ChaCha20 一致，跨语言 (C++/Go) 互通验证

### 12.1 ChaCha20 密码学参数

| 参数 | RC4 (原) | ChaCha20 (新) |
|---|---|---|
| 密钥长度 | 16 字节 | 32 字节 (16B encrypt_key 右侧零填充) |
| Nonce | 无 | 12 字节随机 (encrypt 时生成) |
| 加密包膨胀 | 0 字节 | +12 字节 (Nonce 前置) |
| 轮数 | N/A | 20 轮 (10 次双轮) |
| 算法结构 | 流密码 (KSA+PRGA) | 分组密码 CTR 模式 (每 64 字节一个 block) |
| 标准 | 无 (1994 私有设计) | RFC 8439 |

### 12.2 C++ 实现 (Agent 侧)

#### 文件: `Crypt.h` / `Crypt.cpp`

新增两个顶层 API：

```cpp
// 加密：在 data 首部预留 12B Nonce，ChaCha20 XOR 后整体长度 = dataLen + 12
void ChaCha20EncryptInPlace(PBYTE data, DWORD dataLen, PBYTE key, DWORD keyLen);

// 解密：从 data[0..11] 读 Nonce，XOR 解密 data[12..]，memmove 到 data[0..]，返回 dataLen - 12
DWORD ChaCha20DecryptInPlace(PBYTE data, DWORD dataLen, PBYTE key, DWORD keyLen);
```

**关键设计决策：**
- Encrypt 调用方需确保 buffer 有 12 字节额外空间 (`EnsureCapacity(12)` 或 `malloc(N+12)`)
- Decrypt 返回缩减后的长度，调用方须用返回值更新尺寸变量
- 16 字节 RC4 key 零填充为 32 字节 ChaCha20 key，保证向后兼容 `encrypt_key` 字段

**ChaCha20 分组密码核心 (`chacha20_block`):**
- 常量: `"expand 32-byte k"` (c0-c3)
- 状态矩阵: 16 个 uint32，4×4 布局
- 每轮 8 次 Quarter Round (4 列操作 + 4 对角线操作)
- 10 次双轮 = 20 轮，与 RFC 8439 一致
- 每个 block 生成 64 字节 keystream

#### Agent 调用点变更汇总

| 文件 | 函数 | 变更 |
|---|---|---|
| `Agent.cpp` | `BuildBeat` | `EnsureCapacity(12)` → `ChaCha20EncryptInPlace`；beat_size +12 (HTTP/DNS) / +16 (TCP/SMB) |
| `AgentConfig.cpp` | profile 解密 | `DecryptRC4` → `ChaCha20DecryptInPlace` |
| `ConnectorHTTP.cpp` | `Exchange` | 加密: 临时 buffer `plainSize+12`；解密: `recvSize -= 12` |
| `ConnectorTCP.cpp` | `Exchange` | 同 HTTP 模式 |
| `ConnectorSMB.cpp` | `Exchange` | 同 HTTP 模式 |
| `ConnectorDNS.cpp` | 9 个调用点 | `SetProfile`, `Exchange` (encrypt/decrypt), `SendHeartbeat`, `SendAck`, `Upload` frame, `Download` req/resp — 所有固定大小 buffer 扩容 +12 |

**ConnectorDNS 特殊处理：**
DNS 协议有 7 组固定大小的内部 buffer，因 RC4 无膨胀而 ChaCha20 有 +12B 开销：
- `kAckDataSize`: 12 → 24 (`ackData[24]`)
- `kReqDataSize`: 8 → 20 (`reqData[20]`)
- `hbLabel[48]`, `ackLabel[48]`, `reqLabel[40]` — 对应 Base32Encode 的 `size+12`
- Upload frame: `MemAllocLocal(frameSize+12)`, 释放时同步 `+12`
- Download 解密: `ChaCha20DecryptInPlace` → `binLen -= 12`

### 12.3 Go 实现 (Server 侧)

#### 文件: `beacon_agent/pl_utils.go`

删除 `"crypto/rc4"` 导入，新增 ChaCha20 全套实现：

```go
func rotl32(v uint32, c uint32) uint32           // 与 C++ ROTL32 位操作一致
func qr(a, b, c, d *uint32)                        // Quarter Round
func chacha20Block(key *[8]uint32, nonce *[3]uint32, counter uint32, out *[16]uint32)
func chacha20XOR(dst, src, key, nonce []byte)      // 流 XOR，按 64B block 推进
func ChaCha20Encrypt(plaintext, key []byte) ([]byte, error)  // 生成 12B nonce，返回 nonce+ciphertext
func ChaCha20Decrypt(ciphertext, key []byte) ([]byte, error) // 提取 nonce，返回 plaintext
```

#### 文件: `beacon_agent/pl_main.go`

| 函数 | 变更 |
|---|---|
| `GenerateProfiles` (L507) | `RC4Crypt(packedParams, encryptKey)` → `ChaCha20Encrypt(packedParams, encryptKey)` |
| `Encrypt` (L811) | `return ChaCha20Encrypt(data, key)` |
| `Decrypt` (L817) | `return ChaCha20Decrypt(data, key)` |

#### 文件: `beacon_listener_http/pl_transport.go`

- `handleHI` (beat 解密): `ChaCha20Decrypt` 替换 `rc4.NewCipher + XORKeyStream`
- 新增 ChaCha20 工具函数: `chacha20Block`, `chacha20XOR`, `ChaCha20Decrypt`

#### 文件: `beacon_listener_tcp/pl_main.go`

- `InternalHandler`: 先 `ChaCha20Decrypt` 解密 → 解析 `padLen` → 跳过 1+padLen → 读取 agentType(4B) + agentId(4B)
- 新增完整 ChaCha20 辅助函数

#### 文件: `beacon_listener_smb/pl_main.go`

- 与 TCP Listener 相同变更

#### 文件: `beacon_listener_dns/pl_transport.go`

- 新增 ChaCha20 原语 (`chacha20QR`, `chacha20Block`, `chacha20XOR`)
- Beat 解密 (handleHI): `ChaCha20DecryptDNS` + padding skip
- 新增包装函数: `chaCha20EncryptHex`, `chaCha20DecryptHex` — 自动 hex 解码 encrypt_key
- 替换 4 处 `rc4Crypt` 调用：3 处解密 (L307/L350/L402) + 1 处加密 (L714)

### 12.4 Go 文件修改列表

| 文件 | 变更类型 |
|---|---|
| `extenders/beacon_agent/pl_utils.go` | `crypto/rc4` → ChaCha20 全套实现，保留 `ChaCha20Encrypt`/`ChaCha20Decrypt` 顶层接口 |
| `extenders/beacon_agent/pl_main.go` | 3 处调用点替换 + 修复误删的 Decrypt 函数 |
| `extenders/beacon_listener_http/pl_transport.go` | 删除 rc4 import，beat 解密 + ChaCha20 helpers |
| `extenders/beacon_listener_tcp/pl_main.go` | 删除 rc4 import，InternalHandler 解密 + padding skip + ChaCha20 helpers |
| `extenders/beacon_listener_smb/pl_main.go` | 同 TCP Listener |
| `extenders/beacon_listener_dns/pl_transport.go` | 删除 rc4 import，ChaCha20 全套 + hex 包装 + 4 处调用点替换 |

### 12.5 C++ 文件修改列表

| 文件 | 变更类型 |
|---|---|
| `Crypt.h` | 声明 `ChaCha20EncryptInPlace` / `ChaCha20DecryptInPlace` |
| `Crypt.cpp` | 实现 ChaCha20 全套 (`ROTL32`, `QR`, `chacha20_block`, `chacha20_xor`, 顶层 API) |
| `Agent.cpp` | `BuildBeat`: EnsureCapacity(12) + ChaCha20EncryptInPlace + beat_size 调整 |
| `AgentConfig.cpp` | Profile 解密改用 ChaCha20DecryptInPlace |
| `ConnectorHTTP.cpp` | 加密临时 buffer +12，解密 recvSize -12 |
| `ConnectorTCP.cpp` | 同 HTTP |
| `ConnectorSMB.cpp` | 同 HTTP |
| `ConnectorDNS.cpp` | 9 处调用点替换，固定 buffer 扩容，Base32 编码长度修正 |

### 12.6 密码学一致性验证

Go 和 C++ 的 ChaCha20 实现在以下层面完全一致：

- **Quarter Round**: 相同的 ROTL32 移位量 (16, 12, 8, 7)
- **状态矩阵初始化**: 相同的常量 (0x61707865, 0x3320646e, 0x79622d32, 0x6b206574)
- **双轮模式**: 列操作 (0-4-8-12, 1-5-9-13, 2-6-10-14, 3-7-11-15) + 对角线操作 (0-5-10-15, 1-6-11-12, 2-7-8-13, 3-4-9-14)
- **密钥展开**: 16 字节 `encrypt_key` + 16 字节零填充 = 32 字节 ChaCha20 key
- **Nonce 处理**: 12 字节随机 Nonce 前置，解密时从 ciphertext 前 12 字节提取
- **端点序**: Little Endian (binary.LittleEndian / 直接内存操作)

### 12.7 编译坑点记录

> 编译环境: Kali Linux 6.19.11, Go 1.25.4, MinGW GCC 15-win32 (x64/x86)

#### 坑点 1: `crypto/rand` 与 `math/rand/v2` 包名冲突

**症状:**
```
pl_utils.go:11:2: rand redeclared in this block
pl_utils.go:6:2: other declaration of rand
pl_utils.go:11:2: "math/rand/v2" imported as rand and not used
pl_utils.go:116:23: undefined: rand.Uint32
pl_utils.go:134:46: undefined: rand.Uint32
```

**原因:** 原始 v1.2 已经 `import "math/rand/v2"` (用于 `rand.Uint32()` 生成 TaskID)，修改时新增 `import "crypto/rand"` (用于 ChaCha20 nonce 生成)。两个包默认都叫 `rand`，产生冲突。

**修复:** `"crypto/rand"` → `crand "crypto/rand"`，Nonce 生成改用 `crand.Read()`。`math/rand/v2` 保留给非安全场景的 `rand.Uint32()`。

#### 坑点 2: `agentId :=` 重复短声明

**症状 (TCP/SMB listener):**
```
pl_main.go:186:10: no new variables on left side of :=
pl_main.go:183:10: no new variables on left side of :=
```

**原因:** `InternalHandler` 入口已声明 `var agentId = ""`，但 ChaCha20 padding skip 代码块中写成了 `agentId :=`。Go 的 `:=` 要求左侧至少有一个新变量，`agentId` 已存在导致编译失败。

**修复:** `agentId :=` → `agentId =`

#### 坑点 3: `Crypt.h` 缺少 `#include <windows.h>`

**症状:**
```
Crypt.h:3:6: error: 'PBYTE' was not declared in this scope
Crypt.h:3:41: error: 'DWORD' was not declared in this scope
Crypt.h:5:1: error: 'DWORD' does not name a type
```

**原因:** 原始 v1.2 的 `Crypt.h` 使用 `unsigned char*` 和 `int` 等标准 C 类型，不依赖 Windows 头文件。修改后的 ChaCha20 API 使用了 `PBYTE`/`DWORD` 等 Win32 类型别名，但 `Crypt.h` 未引入 `<windows.h>`。`Crypt.cpp` 虽通过 `utils.h` 间接包含了 `<windows.h>`，但头文件编译时 `Crypt.h` 是独立解析的。

**修复:** 
1. `Crypt.h` 添加 `#include <windows.h>`
2. `PBYTE` → `BYTE*` (匹配项目中 `utils.h` 的类型约定)

#### 坑点 4: 构建脚本 log 路径

**症状:** extender 编译失败但 ext_*.log 文件为空或不存在。

**原因:** 第一版 `build_monitor.sh` 在子 shell `(cd "$dir" && make ...)` 中写入相对路径 `build_logs/`，cd 后工作目录变为了 extender 子目录，log 路径解析为 `extenders/xxx/build_logs/...`（不存在）。

**修复:** `LOG_DIR` 使用绝对路径 `$SCRIPT_DIR/build_logs`，log 文件路径在子 shell 执行前展开。

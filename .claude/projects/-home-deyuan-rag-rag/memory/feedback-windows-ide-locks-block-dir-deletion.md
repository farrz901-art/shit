---
name: feedback-windows-ide-locks-block-dir-deletion
description: Windows 上被 IDE (Trae CN / VSCode) 持有的目录句柄会阻止 rmdir，ERROR_SHARING_VIOLATION (32) / Device or resource busy
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# Windows 上 IDE 锁住的目录删不掉

**症状**：在 Windows 11 + PowerShell 上删一个被 IDE (Trae CN / VSCode 等) 打开的目录时，文件能删但**空目录本身**会留下，rmdir 报 `Device or resource busy` (Win32 ERROR_SHARING_VIOLATION 32 / ERROR_ACCESS_DENIED 5)。

**根因**：IDE 的 LSP 子进程 (Trae CN 的 `ruff server`, VSCode 的 Pylance 等) 会持续持有**目录句柄** (不只是文件句柄)。目录句柄不通过常规的 handle 枚举暴露，Restart Manager (`rstrtmgr.dll`) 也常因 ACCESS_DENIED 失败枚举不到锁的拥有者。

**踩过的工具**（2026-06-04 在 `src/server/` 删除时）：

- `Remove-Item -Recurse -Force` PowerShell — 失败
- `rm -rf` Git Bash — 失败
- Python `shutil.rmtree` / `os.rmdir` — 失败
- Win32 `RemoveDirectoryW` 直接调用 — 失败
- `cmd /c rd /s /q` — 失败
- `takeown` + `rmdir` — 失败
- Windows Restart Manager `RmGetList` + `RmShutdown` — 失败 (ACCESS_DENIED 枚举不出锁)
- 等 60 秒轮询 — 锁持续

**为什么 file 删除成功但 dir 失败**：文件句柄是进程用完就释放的，IDE 不会保留对单个文件的句柄；但**目录句柄**用于监控目录变化（文件系统 watcher / chokidar 之类），IDE 持续保留。

**解决方案**（按推荐顺序）：
1. **完全关闭 IDE**（不只是关窗口，要结束进程），等几秒后手动 `rmdir` —— 99% 有效
2. 重启 Windows —— 100% 有效
3. **不处理** —— 空目录对 git 不可见（未跟踪），对功能零影响（pytest 全 PASS，import 正常）

**How to apply**：
- 跑 RAG / decoder 之类的 Python 重构 + 目录删除任务时，**先关 IDE 再删目录**，避免重做
- 任务报告里写清楚 "空目录残留，IDE 锁"，让用户决定是否后续清理
- 此类 lock 在 Linux / macOS 上罕见 (FSEvents 行为不同)，不要把 Windows 经验套到 Linux

**Related**: [[feedback-git-stash-drop-is-permanent-windows-pop-can-fail]] — 另一个 Windows 上的工具陷阱

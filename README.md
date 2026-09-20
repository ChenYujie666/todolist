# PyQt6 Todo List（桌面置顶）

一个本地运行的待办事项桌面应用，支持状态分组、排序、软删除与恢复、悬浮球、系统托盘，以及 JSON 导入导出和自动备份。

## 安装与运行

需要 Python 3.10 或更新版本，推荐使用 Python 3.12（与 CI 一致）。Windows 打包需要在 Windows 上执行。

在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

不需要激活虚拟环境。`requirements.txt` 固定了 PyQt6 与 PyInstaller 版本，运行和打包使用同一个环境。

Linux/macOS 的源码运行方式：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## 使用

- 输入内容后点击「添加」或回车；双击条目编辑内容。
- 勾选复选框标记完成，也可通过状态下拉框切换「正在进行」「稍后进行」「已完成」。
- 删除会将条目移到「已删除」分组，可右键恢复。该分组默认隐藏，可在「菜单 → 隐藏状态」中取消隐藏。
- 「菜单」支持按创建/勾选时间排序、按状态筛选；点击分组标题可折叠分组。
- 点击「↑」切换置顶，点击「●」收起为悬浮球。悬浮球可拖动，点击恢复窗口。悬浮球下方会按当前任务栏实际固定的应用数量显示快捷按钮，并按 Windows 的 Win+1、Win+2……顺序匹配图标；点击同一个按钮再次切换时，沿用 Windows 原生行为将当前应用最小化。
- 系统托盘可用时，默认启动为悬浮球，关闭窗口也会收起；要完全退出，右键托盘图标选择「退出」，或关闭托盘模式后关闭窗口。
- 「菜单 → JSON」提供导出（Save JSON）、导入（Load JSON）、恢复最近一次备份和查看/复制数据路径。导入和恢复会替换当前列表。

## 数据与备份

数据在修改后自动保存。Windows 默认优先使用 `%LOCALAPPDATA%/TodoList/.todos.json`；会优先复用已有数据文件，并在新建目录不可写时尝试其他用户目录。Linux/macOS 默认使用 `~/.todolist/.todos.json`。实际路径以「菜单 → JSON → 数据路径」为准。

备份保存在数据文件旁的 `backups` 目录：最近 20 次历史副本，以及按日/周/月/年分组的备份。导出的 JSON 可用于手动迁移或长期备份；打包程序不包含个人待办数据。

## 测试

测试使用 Python 标准库 `unittest`，GUI 回归测试还需要已安装的 PyQt6。测试通过临时目录隔离数据，并以离屏模式运行，不打开桌面窗口。

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

Linux/macOS：

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Linux 仍需 Qt 运行库；Ubuntu 可安装 `libegl1` 和 `libopengl0`。CI 会在 Windows 和 Ubuntu 上运行同一套测试。

## 打包 Windows 单文件 EXE

安装依赖后执行：

```powershell
.\build.ps1
```

脚本优先使用项目的 `.venv`，否则使用当前 `PATH` 中的 `python`；也可以通过 `-PythonExecutable` 指定 Python 路径。脚本可从其他工作目录调用，构建失败时会报错。若本机策略阻止执行脚本，可在项目目录直接运行等价命令：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean TodoList.spec
```

输出为 `dist/TodoList.exe`。本地构建、CI 与 Release 统一使用已提交的 `TodoList.spec`，同时嵌入 EXE 图标和运行时托盘图标 `assets/icons/todolist.ico`。

## CI 与发布

推送或创建 Pull Request 后，CI 会执行回归测试并构建 Windows EXE，可从工作流的 `TodoList-windows-exe` artifact 下载。

推送以 `TodoList` 开头的标签会构建该标签并发布 GitHub Release。手动运行 Release 工作流时，需要填写一个已经存在、以 `TodoList` 开头的标签；工作流会检出该标签，测试通过后再发布对应 EXE。

# PyQt6 Todo List（桌面置顶）

一个简洁的待办事项桌面应用，支持：

- 新增/完成/删除待办
- 自动保存到用户目录隐藏文件（Windows 会自动选择可写目录）
- 窗口置顶（可开关）

## 运行

```bash
pip install -r requirements.txt
python main.py
```

## 打包（PyInstaller 单文件）

```powershell
./build.ps1
```

输出文件：`dist/TodoList.exe`

你也可以手动执行：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name TodoList main.py
```

## 使用

- 在输入框输入内容后，点击「添加」或回车
- 勾选复选框标记完成
- 点击「删除」移除条目
- 勾选「窗口置顶」让窗口始终显示在最前
- 数据文件会写入隐藏目录，不会在项目目录下直接暴露 `todos.json`
- Windows 默认优先：`%LOCALAPPDATA%/TodoList/.todos.json`，若无权限会自动降级到其他可写目录

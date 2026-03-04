import json
import os
import sys
import importlib.util
import ctypes
import tempfile
from datetime import datetime
from dataclasses import dataclass, asdict

def _prepare_pyqt6_dll_path() -> None:
    if os.name != "nt":
        return

    spec = importlib.util.find_spec("PyQt6")
    if not spec or not spec.submodule_search_locations:
        return

    pyqt6_dir = spec.submodule_search_locations[0]
    qt_bin_dir = os.path.join(pyqt6_dir, "Qt6", "bin")
    if not os.path.isdir(qt_bin_dir):
        return

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(qt_bin_dir)

    os.environ["PATH"] = qt_bin_dir + os.pathsep + os.environ.get("PATH", "")


_prepare_pyqt6_dll_path()

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


DATA_FILE = "todos.json"
APP_DIR_NAME = "TodoList"
HIDDEN_DATA_FILE = ".todos.json"


@dataclass
class TodoItem:
    text: str
    done: bool = False
    created_at: str = ""
    checked_at: str | None = None


class TodoApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.todos: list[TodoItem] = []
        self._data_path: str | None = None

        self.setWindowTitle("Todo List")
        self.setMinimumWidth(380)
        self.resize(420, 560)

        self.title_label = QLabel("我的待办")
        self.title_label.setObjectName("titleLabel")

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入待办内容，按回车快速添加…")
        self.input_box.returnPressed.connect(self.add_todo)

        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.add_todo)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.add_button)

        self.todo_list = QListWidget()

        self.pin_checkbox = QCheckBox("窗口置顶")
        self.pin_checkbox.stateChanged.connect(self.toggle_topmost)

        self.path_button = QPushButton("数据路径")
        self.path_button.clicked.connect(self.show_data_path)

        self.menu_button = QPushButton("菜单")
        self.menu = QMenu(self)
        self.json_menu = self.menu.addMenu("JSON")

        self.save_json_action = QAction("Save JSON", self)
        self.save_json_action.triggered.connect(self.export_json_file)
        self.json_menu.addAction(self.save_json_action)

        self.load_json_action = QAction("Load JSON", self)
        self.load_json_action.triggered.connect(self.import_json_file)
        self.json_menu.addAction(self.load_json_action)

        self.menu_button.setMenu(self.menu)

        footer_layout = QHBoxLayout()
        footer_layout.addWidget(self.pin_checkbox)
        footer_layout.addStretch()
        footer_layout.addWidget(self.menu_button)
        footer_layout.addWidget(self.path_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.title_label)
        main_layout.addLayout(input_layout)
        main_layout.addWidget(self.todo_list)
        main_layout.addLayout(footer_layout)
        self.setLayout(main_layout)

        self.setStyleSheet(
            """
            QWidget {
                background: #f5f7fb;
                font-size: 14px;
            }
            #titleLabel {
                font-size: 20px;
                font-weight: 700;
                color: #1f2937;
            }
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 10px;
                background: white;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                background: #2563eb;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                background: white;
                padding: 4px;
            }
            """
        )

        self.load_todos()

    def get_data_path(self) -> str:
        if self._data_path:
            return self._data_path

        candidates: list[str] = []
        if os.name == "nt":
            local_app_data = os.getenv("LOCALAPPDATA")
            roaming_app_data = os.getenv("APPDATA")
            if local_app_data:
                candidates.append(os.path.join(local_app_data, APP_DIR_NAME))
            if roaming_app_data:
                candidates.append(os.path.join(roaming_app_data, APP_DIR_NAME))
            candidates.append(os.path.join(os.path.expanduser("~"), APP_DIR_NAME))
            candidates.append(os.path.join(tempfile.gettempdir(), APP_DIR_NAME))
        else:
            candidates.append(os.path.join(os.path.expanduser("~"), f".{APP_DIR_NAME.lower()}"))
            candidates.append(os.path.join(tempfile.gettempdir(), APP_DIR_NAME.lower()))

        for app_dir in candidates:
            try:
                os.makedirs(app_dir, exist_ok=True)
                probe_file = os.path.join(app_dir, ".write_test")
                with open(probe_file, "w", encoding="utf-8") as file:
                    file.write("ok")
                os.remove(probe_file)
                self._mark_hidden(app_dir)
                self._data_path = os.path.join(app_dir, HIDDEN_DATA_FILE)
                return self._data_path
            except OSError:
                continue

        fallback = os.path.join(tempfile.gettempdir(), HIDDEN_DATA_FILE)
        self._data_path = fallback
        return self._data_path

    def _mark_hidden(self, path: str) -> None:
        if os.name != "nt":
            return

        try:
            FILE_ATTRIBUTE_HIDDEN = 0x02
            current = ctypes.windll.kernel32.GetFileAttributesW(path)
            if current == -1:
                return
            ctypes.windll.kernel32.SetFileAttributesW(path, current | FILE_ATTRIBUTE_HIDDEN)
        except Exception:
            return

    def _get_legacy_data_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), DATA_FILE)

    def add_todo(self) -> None:
        text = self.input_box.text().strip()
        if not text:
            return

        self.todos.append(TodoItem(text=text, done=False, created_at=self._now_text(), checked_at=None))
        self.input_box.clear()
        self.refresh_list()
        self.save_todos()

    def _now_text(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def refresh_list(self) -> None:
        self.todo_list.clear()
        for index, todo in enumerate(self.todos):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 4, 8, 4)

            done_checkbox = QCheckBox(todo.text)
            done_checkbox.setChecked(todo.done)
            checked_text = todo.checked_at if todo.checked_at else "未完成"
            done_checkbox.setToolTip(f"创建时间: {todo.created_at}\n勾选时间: {checked_text}")
            done_checkbox.stateChanged.connect(
                lambda state, i=index: self.toggle_done(i, state == Qt.CheckState.Checked.value)
            )

            time_label = QLabel(f"创建: {todo.created_at}    勾选: {checked_text}")
            time_label.setStyleSheet("color: #6b7280; font-size: 12px;")

            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(2)
            left_layout.addWidget(done_checkbox)
            left_layout.addWidget(time_label)

            delete_button = QPushButton("删除")
            delete_button.setFixedWidth(58)
            delete_button.clicked.connect(lambda _, i=index: self.delete_todo(i))

            row_layout.addWidget(left_widget)
            row_layout.addStretch()
            row_layout.addWidget(delete_button)

            item = QListWidgetItem(self.todo_list)
            item.setSizeHint(row_widget.sizeHint())
            self.todo_list.addItem(item)
            self.todo_list.setItemWidget(item, row_widget)

    def toggle_done(self, index: int, done: bool) -> None:
        if 0 <= index < len(self.todos):
            self.todos[index].done = done
            self.todos[index].checked_at = self._now_text() if done else None
            self.refresh_list()
            self.save_todos()

    def delete_todo(self, index: int) -> None:
        if 0 <= index < len(self.todos):
            del self.todos[index]
            self.refresh_list()
            self.save_todos()

    def save_todos(self) -> None:
        data = [asdict(todo) for todo in self.todos]
        data_path = self.get_data_path()
        try:
            with open(data_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            self._mark_hidden(data_path)
        except OSError:
            self._data_path = None
            retry_path = self.get_data_path()
            try:
                with open(retry_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
                self._mark_hidden(retry_path)
            except OSError:
                return

    def load_todos(self) -> None:
        path = self.get_data_path()
        if not os.path.exists(path):
            legacy_path = self._get_legacy_data_path()
            if os.path.exists(legacy_path):
                try:
                    with open(legacy_path, "r", encoding="utf-8") as file:
                        data = json.load(file)
                    self.todos = [
                        TodoItem(
                            text=item.get("text", ""),
                            done=item.get("done", False),
                            created_at=item.get("created_at") or self._now_text(),
                            checked_at=item.get("checked_at"),
                        )
                        for item in data
                    ]
                    self.save_todos()
                except (json.JSONDecodeError, OSError):
                    self.todos = []
                self.refresh_list()
            return

        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.todos = [
                TodoItem(
                    text=item.get("text", ""),
                    done=item.get("done", False),
                    created_at=item.get("created_at") or self._now_text(),
                    checked_at=item.get("checked_at"),
                )
                for item in data
            ]
            self.refresh_list()
        except (json.JSONDecodeError, OSError):
            self.todos = []

    def toggle_topmost(self, state: int) -> None:
        is_topmost = state == Qt.CheckState.Checked.value
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, is_topmost)
        self.show()

    def export_json_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save JSON",
            "todos.json",
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        data = [asdict(todo) for todo in self.todos]
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Save JSON", "保存成功")
        except OSError:
            QMessageBox.warning(self, "Save JSON", "保存失败")

    def import_json_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load JSON",
            "",
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            QMessageBox.warning(self, "Load JSON", "读取失败，文件格式不正确")
            return

        if not isinstance(data, list):
            QMessageBox.warning(self, "Load JSON", "读取失败，JSON 必须是数组")
            return

        todos: list[TodoItem] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            done = bool(item.get("done", False))
            created_at = item.get("created_at") or self._now_text()
            checked_at = item.get("checked_at")
            if done and not checked_at:
                checked_at = self._now_text()
            if not done:
                checked_at = None
            todos.append(TodoItem(text=text, done=done, created_at=created_at, checked_at=checked_at))

        self.todos = todos
        self.refresh_list()
        self.save_todos()
        QMessageBox.information(self, "Load JSON", "加载成功")

    def show_data_path(self) -> None:
        data_path = self.get_data_path()
        message_box = QMessageBox(self)
        message_box.setWindowTitle("数据文件位置")
        message_box.setText(data_path)

        copy_button = message_box.addButton("复制路径", QMessageBox.ButtonRole.ActionRole)
        message_box.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
        message_box.exec()

        if message_box.clickedButton() == copy_button:
            QApplication.clipboard().setText(data_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TodoApp()
    window.show()
    sys.exit(app.exec())

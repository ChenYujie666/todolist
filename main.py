import json
import os
import sys
import importlib.util
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
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


DATA_FILE = "todos.json"


@dataclass
class TodoItem:
    text: str
    done: bool = False


class TodoApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.todos: list[TodoItem] = []

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

        footer_layout = QHBoxLayout()
        footer_layout.addWidget(self.pin_checkbox)
        footer_layout.addStretch()

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
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), DATA_FILE)

    def add_todo(self) -> None:
        text = self.input_box.text().strip()
        if not text:
            return

        self.todos.append(TodoItem(text=text, done=False))
        self.input_box.clear()
        self.refresh_list()
        self.save_todos()

    def refresh_list(self) -> None:
        self.todo_list.clear()
        for index, todo in enumerate(self.todos):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 4, 8, 4)

            done_checkbox = QCheckBox(todo.text)
            done_checkbox.setChecked(todo.done)
            done_checkbox.stateChanged.connect(
                lambda state, i=index: self.toggle_done(i, state == Qt.CheckState.Checked.value)
            )

            delete_button = QPushButton("删除")
            delete_button.setFixedWidth(58)
            delete_button.clicked.connect(lambda _, i=index: self.delete_todo(i))

            row_layout.addWidget(done_checkbox)
            row_layout.addStretch()
            row_layout.addWidget(delete_button)

            item = QListWidgetItem(self.todo_list)
            item.setSizeHint(row_widget.sizeHint())
            self.todo_list.addItem(item)
            self.todo_list.setItemWidget(item, row_widget)

    def toggle_done(self, index: int, done: bool) -> None:
        if 0 <= index < len(self.todos):
            self.todos[index].done = done
            self.save_todos()

    def delete_todo(self, index: int) -> None:
        if 0 <= index < len(self.todos):
            del self.todos[index]
            self.refresh_list()
            self.save_todos()

    def save_todos(self) -> None:
        data = [asdict(todo) for todo in self.todos]
        with open(self.get_data_path(), "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def load_todos(self) -> None:
        path = self.get_data_path()
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.todos = [TodoItem(text=item.get("text", ""), done=item.get("done", False)) for item in data]
            self.refresh_list()
        except (json.JSONDecodeError, OSError):
            self.todos = []

    def toggle_topmost(self, state: int) -> None:
        is_topmost = state == Qt.CheckState.Checked.value
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, is_topmost)
        self.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TodoApp()
    window.show()
    sys.exit(app.exec())

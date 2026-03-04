import json
import os
import sys
import importlib.util
import ctypes
import tempfile
import shutil
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

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


DATA_FILE = "todos.json"
APP_DIR_NAME = "TodoList"
HIDDEN_DATA_FILE = ".todos.json"
BACKUP_DIR_NAME = "backups"
MAX_BACKUP_FILES = 20
MAX_DAILY_BACKUPS = 30
MAX_WEEKLY_BACKUPS = 26
MAX_MONTHLY_BACKUPS = 24
MAX_YEARLY_BACKUPS = 10
STATUS_IN_PROGRESS = "正在进行"
STATUS_LATER = "稍后进行"
STATUS_DONE = "已完成"
STATUS_ALL = "全部"
STATUS_OPTIONS = [STATUS_IN_PROGRESS, STATUS_LATER, STATUS_DONE]


@dataclass
class TodoItem:
    text: str
    done: bool = False
    created_at: str = ""
    checked_at: str | None = None
    status: str = STATUS_IN_PROGRESS


class TodoApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.todos: list[TodoItem] = []
        self._data_path: str | None = None
        self.current_status_filter = STATUS_ALL
        self.current_sort_mode = "created_desc"

        self.setWindowTitle("Todo List")
        self.setMinimumWidth(380)
        self.resize(420, 560)

        self.title_label = QLabel("我的待办")
        self.title_label.setObjectName("titleLabel")

        self.top_bar = QWidget()
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(6)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #374151; font-size: 12px;")

        self.save_status_label = QLabel("")
        self.save_status_label.setStyleSheet("color: #6b7280; font-size: 12px;")

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入待办内容，按回车快速添加…")
        self.input_box.returnPressed.connect(self.add_todo)

        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.add_todo)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.add_button)

        self.todo_list = QListWidget()
        self.todo_list.itemDoubleClicked.connect(self.edit_todo_item)

        self.pin_button = QPushButton("↑")
        self.pin_button.setObjectName("topmostButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(True)
        self.pin_button.setToolTip("切换窗口是否置顶")
        self.pin_button.clicked.connect(self.toggle_topmost)

        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.pin_button)

        self.menu_button = QPushButton("菜单")
        self.menu = QMenu(self)
        self.json_menu = self.menu.addMenu("JSON")
        self.sort_menu = self.menu.addMenu("排序")
        self.filter_menu = self.menu.addMenu("按状态分类")

        self.save_json_action = QAction("Save JSON", self)
        self.save_json_action.triggered.connect(self.export_json_file)
        self.json_menu.addAction(self.save_json_action)

        self.load_json_action = QAction("Load JSON", self)
        self.load_json_action.triggered.connect(self.import_json_file)
        self.json_menu.addAction(self.load_json_action)

        self.restore_backup_action = QAction("恢复最近一次备份", self)
        self.restore_backup_action.triggered.connect(self.restore_latest_backup)
        self.json_menu.addAction(self.restore_backup_action)

        self.show_data_path_action = QAction("数据路径", self)
        self.show_data_path_action.triggered.connect(self.show_data_path)
        self.json_menu.addAction(self.show_data_path_action)

        self.sort_created_desc_action = QAction("创建时间（新->旧）", self)
        self.sort_created_desc_action.triggered.connect(lambda: self.set_sort_mode("created_desc"))
        self.sort_menu.addAction(self.sort_created_desc_action)

        self.sort_created_asc_action = QAction("创建时间（旧->新）", self)
        self.sort_created_asc_action.triggered.connect(lambda: self.set_sort_mode("created_asc"))
        self.sort_menu.addAction(self.sort_created_asc_action)

        self.sort_checked_desc_action = QAction("勾选时间（新->旧）", self)
        self.sort_checked_desc_action.triggered.connect(lambda: self.set_sort_mode("checked_desc"))
        self.sort_menu.addAction(self.sort_checked_desc_action)

        self.sort_checked_asc_action = QAction("勾选时间（旧->新）", self)
        self.sort_checked_asc_action.triggered.connect(lambda: self.set_sort_mode("checked_asc"))
        self.sort_menu.addAction(self.sort_checked_asc_action)

        self.filter_all_action = QAction("全部", self)
        self.filter_all_action.triggered.connect(lambda: self.set_status_filter(STATUS_ALL))
        self.filter_menu.addAction(self.filter_all_action)

        self.filter_in_progress_action = QAction(STATUS_IN_PROGRESS, self)
        self.filter_in_progress_action.triggered.connect(lambda: self.set_status_filter(STATUS_IN_PROGRESS))
        self.filter_menu.addAction(self.filter_in_progress_action)

        self.filter_later_action = QAction(STATUS_LATER, self)
        self.filter_later_action.triggered.connect(lambda: self.set_status_filter(STATUS_LATER))
        self.filter_menu.addAction(self.filter_later_action)

        self.filter_done_action = QAction(STATUS_DONE, self)
        self.filter_done_action.triggered.connect(lambda: self.set_status_filter(STATUS_DONE))
        self.filter_menu.addAction(self.filter_done_action)

        self.menu_button.setMenu(self.menu)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        footer_layout.addWidget(self.menu_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.top_bar)
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.stats_label)
        main_layout.addLayout(input_layout)
        main_layout.addWidget(self.todo_list)
        main_layout.addLayout(footer_layout)
        main_layout.addWidget(self.save_status_label)
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
            #topmostButton {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0;
                border-radius: 6px;
                background: #f3f4f6;
                color: #111827;
                border: 1px solid #d1d5db;
                font-weight: 700;
            }
            #topmostButton:hover {
                background: #e5e7eb;
            }
            #topmostButton:checked {
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
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
        self.toggle_topmost(True)

    def get_data_path(self) -> str:
        if self._data_path:
            return self._data_path

        candidates = self._get_data_dir_candidates()

        for app_dir in candidates:
            existing_path = os.path.join(app_dir, HIDDEN_DATA_FILE)
            if os.path.isfile(existing_path):
                self._data_path = existing_path
                return self._data_path

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

    def _get_data_dir_candidates(self) -> list[str]:
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
        return candidates

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

        self.todos.append(
            TodoItem(
                text=text,
                done=False,
                created_at=self._now_text(),
                checked_at=None,
                status=STATUS_IN_PROGRESS,
            )
        )
        self.input_box.clear()
        self.refresh_list()
        self.save_todos()

    def _now_text(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def refresh_list(self) -> None:
        self.todo_list.clear()
        self.update_stats_label()

        indexed_todos = list(enumerate(self.todos))
        indexed_todos = self._sort_todos(indexed_todos)

        grouped: dict[str, list[tuple[int, TodoItem]]] = {
            STATUS_IN_PROGRESS: [],
            STATUS_LATER: [],
            STATUS_DONE: [],
        }

        for index, todo in indexed_todos:
            if self.current_status_filter != STATUS_ALL and todo.status != self.current_status_filter:
                continue
            grouped[todo.status].append((index, todo))

        for status in STATUS_OPTIONS:
            todos_in_group = grouped[status]
            if not todos_in_group:
                continue

            header_item = QListWidgetItem(f"{status}（{len(todos_in_group)}）")
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            header_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
            self.todo_list.addItem(header_item)

            for index, todo in todos_in_group:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(8, 4, 8, 4)

                done_checkbox = QCheckBox()
                done_checkbox.setChecked(todo.done)
                checked_text = todo.checked_at if todo.checked_at else "未完成"
                todo_tooltip = (
                    "待办详情\n"
                    f"状态：{todo.status}\n"
                    f"创建时间：{todo.created_at}\n"
                    f"勾选时间：{checked_text}"
                )
                done_checkbox.setToolTip(todo_tooltip)
                done_checkbox.stateChanged.connect(
                    lambda state, i=index: self.toggle_done(i, state == Qt.CheckState.Checked.value)
                )

                task_label = QLabel(todo.text)
                task_label.setToolTip(todo_tooltip)

                status_combo = QComboBox()
                status_combo.addItems(STATUS_OPTIONS)
                status_combo.setCurrentText(todo.status)
                status_combo.currentTextChanged.connect(lambda value, i=index: self.change_status(i, value))
                status_combo.setFixedWidth(100)

                left_widget = QWidget()
                left_layout = QVBoxLayout(left_widget)
                left_layout.setContentsMargins(0, 0, 0, 0)
                left_layout.setSpacing(2)
                title_layout = QHBoxLayout()
                title_layout.setContentsMargins(0, 0, 0, 0)
                title_layout.setSpacing(6)
                title_layout.addWidget(done_checkbox)
                title_layout.addWidget(task_label)
                title_layout.addStretch()
                left_layout.addLayout(title_layout)

                delete_button = QPushButton("删除")
                delete_button.setFixedWidth(58)
                delete_button.clicked.connect(lambda _, i=index: self.delete_todo(i))

                row_layout.addWidget(left_widget)
                row_layout.addStretch()
                row_layout.addWidget(status_combo)
                row_layout.addWidget(delete_button)

                item = QListWidgetItem(self.todo_list)
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setSizeHint(row_widget.sizeHint())
                self.todo_list.addItem(item)
                self.todo_list.setItemWidget(item, row_widget)

    def update_stats_label(self) -> None:
        in_progress_count = sum(1 for todo in self.todos if todo.status == STATUS_IN_PROGRESS)
        later_count = sum(1 for todo in self.todos if todo.status == STATUS_LATER)
        done_count = sum(1 for todo in self.todos if todo.status == STATUS_DONE)
        self.stats_label.setText(
            f"统计：正在进行 {in_progress_count}  |  稍后进行 {later_count}  |  已完成 {done_count}"
        )

    def toggle_done(self, index: int, done: bool) -> None:
        if 0 <= index < len(self.todos):
            self.todos[index].done = done
            if done:
                self.todos[index].status = STATUS_DONE
                self.todos[index].checked_at = self._now_text()
            else:
                self.todos[index].checked_at = None
                if self.todos[index].status == STATUS_DONE:
                    self.todos[index].status = STATUS_IN_PROGRESS
            self.refresh_list()
            self.save_todos()

    def change_status(self, index: int, status: str) -> None:
        if 0 <= index < len(self.todos) and status in STATUS_OPTIONS:
            self.todos[index].status = status
            if status == STATUS_DONE:
                self.todos[index].done = True
                if not self.todos[index].checked_at:
                    self.todos[index].checked_at = self._now_text()
            else:
                self.todos[index].done = False
                self.todos[index].checked_at = None
            self.refresh_list()
            self.save_todos()

    def set_sort_mode(self, mode: str) -> None:
        self.current_sort_mode = mode
        self.refresh_list()

    def set_status_filter(self, status_filter: str) -> None:
        self.current_status_filter = status_filter
        self.refresh_list()

    def _sort_todos(self, indexed_todos: list[tuple[int, TodoItem]]) -> list[tuple[int, TodoItem]]:
        if self.current_sort_mode == "created_asc":
            return sorted(indexed_todos, key=lambda item: item[1].created_at)
        if self.current_sort_mode == "checked_desc":
            return sorted(indexed_todos, key=lambda item: item[1].checked_at or "", reverse=True)
        if self.current_sort_mode == "checked_asc":
            return sorted(indexed_todos, key=lambda item: item[1].checked_at or "")
        return sorted(indexed_todos, key=lambda item: item[1].created_at, reverse=True)

    def delete_todo(self, index: int) -> None:
        if 0 <= index < len(self.todos):
            del self.todos[index]
            self.refresh_list()
            self.save_todos()

    def edit_todo_item(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int):
            return
        if not (0 <= index < len(self.todos)):
            return

        old_text = self.todos[index].text
        new_text, ok = QInputDialog.getText(self, "编辑待办", "事项内容:", text=old_text)
        if not ok:
            return

        new_text = new_text.strip()
        if not new_text:
            return

        self.todos[index].text = new_text
        self.refresh_list()
        self.save_todos()

    def save_todos(self) -> None:
        data = [asdict(todo) for todo in self.todos]
        data_path = self.get_data_path()
        try:
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            self._backup_current_data_file(data_path)
            temp_path = f"{data_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, data_path)
            self._mark_hidden(data_path)
            self.show_save_status("已自动保存", True)
        except OSError:
            self._data_path = None
            retry_path = self.get_data_path()
            try:
                os.makedirs(os.path.dirname(retry_path), exist_ok=True)
                self._backup_current_data_file(retry_path)
                retry_temp_path = f"{retry_path}.tmp"
                with open(retry_temp_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(retry_temp_path, retry_path)
                self._mark_hidden(retry_path)
                self.show_save_status("已自动保存", True)
            except OSError:
                self.show_save_status("自动保存失败", False)
                return

    def _backup_current_data_file(self, data_path: str) -> None:
        if not os.path.exists(data_path):
            return

        backup_dir = os.path.join(os.path.dirname(data_path), BACKUP_DIR_NAME)
        try:
            os.makedirs(backup_dir, exist_ok=True)
            self._mark_hidden(backup_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = os.path.join(backup_dir, f"todos_{timestamp}.json")
            shutil.copy2(data_path, backup_path)
            self._mark_hidden(backup_path)
            self._cleanup_old_backups(backup_dir)
            self._create_periodic_backups(data_path, backup_dir)
        except OSError:
            return

    def _cleanup_old_backups(self, backup_dir: str) -> None:
        try:
            backup_files = [
                os.path.join(backup_dir, name)
                for name in os.listdir(backup_dir)
                if name.lower().endswith(".json")
            ]
            backup_files.sort(key=os.path.getmtime, reverse=True)
            for old_file in backup_files[MAX_BACKUP_FILES:]:
                try:
                    os.remove(old_file)
                except OSError:
                    continue
        except OSError:
            return

    def _create_periodic_backups(self, data_path: str, backup_dir: str) -> None:
        now = datetime.now()
        iso_year, iso_week, _ = now.isocalendar()

        periodic_specs = [
            ("daily", f"daily_{now.strftime('%Y%m%d')}.json", MAX_DAILY_BACKUPS),
            ("weekly", f"weekly_{iso_year}_W{iso_week:02d}.json", MAX_WEEKLY_BACKUPS),
            ("monthly", f"monthly_{now.strftime('%Y%m')}.json", MAX_MONTHLY_BACKUPS),
            ("yearly", f"yearly_{now.strftime('%Y')}.json", MAX_YEARLY_BACKUPS),
        ]

        for folder_name, file_name, keep_count in periodic_specs:
            folder_path = os.path.join(backup_dir, folder_name)
            try:
                os.makedirs(folder_path, exist_ok=True)
                self._mark_hidden(folder_path)

                target_path = os.path.join(folder_path, file_name)
                if not os.path.exists(target_path):
                    shutil.copy2(data_path, target_path)
                    self._mark_hidden(target_path)

                self._cleanup_backup_group(folder_path, keep_count)
            except OSError:
                continue

    def _cleanup_backup_group(self, folder_path: str, keep_count: int) -> None:
        try:
            files = [
                os.path.join(folder_path, name)
                for name in os.listdir(folder_path)
                if name.lower().endswith(".json")
            ]
            files.sort(key=os.path.getmtime, reverse=True)
            for old_file in files[keep_count:]:
                try:
                    os.remove(old_file)
                except OSError:
                    continue
        except OSError:
            return

    def show_save_status(self, text: str, success: bool) -> None:
        color = "#059669" if success else "#dc2626"
        self.save_status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        now_text = datetime.now().strftime("%H:%M:%S")
        self.save_status_label.setText(f"{now_text} {text}")
        QTimer.singleShot(2000, lambda: self.save_status_label.setText(""))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_todos()
        super().closeEvent(event)

    def load_todos(self) -> None:
        path = self.get_data_path()
        self._migrate_from_other_data_paths(path)
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
                            status=item.get("status")
                            if item.get("status") in STATUS_OPTIONS
                            else (STATUS_DONE if item.get("done", False) else STATUS_IN_PROGRESS),
                        )
                        for item in data
                    ]
                    self.save_todos()
                    try:
                        os.remove(legacy_path)
                    except OSError:
                        pass
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
                    status=item.get("status")
                    if item.get("status") in STATUS_OPTIONS
                    else (STATUS_DONE if item.get("done", False) else STATUS_IN_PROGRESS),
                )
                for item in data
            ]
            self.refresh_list()
        except (json.JSONDecodeError, OSError):
            self.todos = []

    def _migrate_from_other_data_paths(self, target_path: str) -> None:
        if os.path.exists(target_path):
            return

        for app_dir in self._get_data_dir_candidates():
            candidate_path = os.path.join(app_dir, HIDDEN_DATA_FILE)
            if os.path.normcase(candidate_path) == os.path.normcase(target_path):
                continue
            if not os.path.exists(candidate_path):
                continue

            try:
                with open(candidate_path, "r", encoding="utf-8") as source_file:
                    data = json.load(source_file)
                if not isinstance(data, list):
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as target_file:
                    json.dump(data, target_file, ensure_ascii=False, indent=2)
                self._mark_hidden(target_path)
                return
            except (json.JSONDecodeError, OSError):
                continue

    def toggle_topmost(self, checked: bool) -> None:
        is_topmost = bool(checked)
        self.pin_button.setToolTip("已置顶" if is_topmost else "未置顶")
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, is_topmost)
        if was_visible:
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
            status = item.get("status") if item.get("status") in STATUS_OPTIONS else None
            if not status:
                status = STATUS_DONE if done else STATUS_IN_PROGRESS
            if done and not checked_at:
                checked_at = self._now_text()
            if not done:
                checked_at = None
            if status == STATUS_DONE:
                done = True
                if not checked_at:
                    checked_at = self._now_text()
            else:
                done = False
                checked_at = None
            todos.append(TodoItem(text=text, done=done, created_at=created_at, checked_at=checked_at, status=status))

        self.todos = todos
        self.refresh_list()
        self.save_todos()
        QMessageBox.information(self, "Load JSON", "加载成功")

    def restore_latest_backup(self) -> None:
        data_path = self.get_data_path()
        backup_dir = os.path.join(os.path.dirname(data_path), BACKUP_DIR_NAME)

        if not os.path.isdir(backup_dir):
            QMessageBox.warning(self, "恢复备份", "未找到备份目录")
            return

        backup_files = [
            os.path.join(backup_dir, name)
            for name in os.listdir(backup_dir)
            if name.lower().endswith(".json")
        ]
        if not backup_files:
            QMessageBox.warning(self, "恢复备份", "没有可恢复的备份")
            return

        backup_files.sort(key=os.path.getmtime, reverse=True)
        latest_backup = backup_files[0]

        try:
            with open(latest_backup, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError("invalid backup format")
        except (json.JSONDecodeError, OSError, ValueError):
            QMessageBox.warning(self, "恢复备份", "备份文件损坏，恢复失败")
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
            status = item.get("status") if item.get("status") in STATUS_OPTIONS else None
            if not status:
                status = STATUS_DONE if done else STATUS_IN_PROGRESS
            if status == STATUS_DONE:
                done = True
                if not checked_at:
                    checked_at = self._now_text()
            else:
                done = False
                checked_at = None

            todos.append(TodoItem(text=text, done=done, created_at=created_at, checked_at=checked_at, status=status))

        self.todos = todos
        self.refresh_list()
        self.save_todos()
        QMessageBox.information(self, "恢复备份", "已恢复最近一次备份")

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

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

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QRegion
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
STATUS_DELETED = "已删除"
STATUS_ALL = "全部"
STATUS_OPTIONS = [STATUS_IN_PROGRESS, STATUS_LATER, STATUS_DONE]
STATUS_FILTER_OPTIONS = [STATUS_IN_PROGRESS, STATUS_LATER, STATUS_DONE, STATUS_DELETED]


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
        self.collapsed_statuses: set[str] = set()
        self.hidden_statuses: set[str] = {STATUS_DELETED}
        self.is_ball_mode = False
        self.normal_geometry: QRect | None = None
        self.normal_layout_margins = (0, 0, 0, 0)
        self.normal_layout_spacing = 6
        self._ball_drag_active = False
        self._ball_drag_moved = False
        self._ball_drag_start = QPoint()
        self._ball_window_start = QPoint()
        self._collapse_anchor_offset = QPoint(0, 0)

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

        self.input_row = QWidget()
        self.input_row.setLayout(input_layout)

        self.todo_list = QListWidget()
        self.todo_list.itemDoubleClicked.connect(self.edit_todo_item)
        self.todo_list.itemClicked.connect(self.handle_list_item_clicked)
        self.todo_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.todo_list.customContextMenuRequested.connect(self.open_todo_context_menu)

        self.pin_button = QPushButton("↑")
        self.pin_button.setObjectName("topmostButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(True)
        self.pin_button.setToolTip("切换窗口是否置顶")
        self.pin_button.clicked.connect(self.toggle_topmost)

        self.collapse_button = QPushButton("●")
        self.collapse_button.setObjectName("collapseButton")
        self.collapse_button.setToolTip("收起为悬浮球")
        self.collapse_button.installEventFilter(self)

        self.menu_button = QPushButton("菜单")
        self.menu = QMenu(self)
        self.json_menu = self.menu.addMenu("JSON")
        self.sort_menu = self.menu.addMenu("排序")
        self.filter_menu = self.menu.addMenu("按状态分类")
        self.hide_status_menu = self.menu.addMenu("隐藏状态")

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

        self.filter_deleted_action = QAction(STATUS_DELETED, self)
        self.filter_deleted_action.triggered.connect(lambda: self.set_status_filter(STATUS_DELETED))
        self.filter_menu.addAction(self.filter_deleted_action)

        self.hide_status_actions: dict[str, QAction] = {}
        for status in STATUS_FILTER_OPTIONS:
            action = QAction(status, self)
            action.setCheckable(True)
            action.setChecked(status in self.hidden_statuses)
            action.toggled.connect(lambda checked, s=status: self.toggle_hidden_status(s, checked))
            self.hide_status_menu.addAction(action)
            self.hide_status_actions[status] = action

        self.menu_button.setMenu(self.menu)

        top_bar_layout.addWidget(self.title_label)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.menu_button)
        top_bar_layout.addWidget(self.pin_button)
        top_bar_layout.addWidget(self.collapse_button)

        self.ball_button = QPushButton("待办")
        self.ball_button.setObjectName("floatingBall")
        self.ball_button.setToolTip("点击恢复窗口")
        self.ball_button.installEventFilter(self)
        self.ball_button.hide()

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addWidget(self.stats_label)
        self.main_layout.addWidget(self.input_row)
        self.main_layout.addWidget(self.todo_list)
        self.main_layout.addWidget(self.save_status_label)
        self.main_layout.addWidget(self.ball_button)
        self.main_layout.setAlignment(self.ball_button, Qt.AlignmentFlag.AlignCenter)
        self.setLayout(self.main_layout)
        self.normal_layout_spacing = self.main_layout.spacing()

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
            #collapseButton {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0;
                border-radius: 14px;
                background: #e5e7eb;
                color: #374151;
                border: 1px solid #d1d5db;
                font-weight: 700;
            }
            #collapseButton:hover {
                background: #d1d5db;
            }
            #floatingBall {
                min-width: 71px;
                max-width: 71px;
                min-height: 71px;
                max-height: 71px;
                border-radius: 35px;
                background: #2563eb;
                color: white;
                font-size: 14px;
                font-weight: 700;
                padding: 0;
            }
            #floatingBall:hover {
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
        self.toggle_topmost(True)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        collapse_button = getattr(self, "collapse_button", None)
        ball_button = getattr(self, "ball_button", None)

        if collapse_button is not None and watched is collapse_button and not self.is_ball_mode:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick) and event.button() == Qt.MouseButton.LeftButton:
                self.enter_ball_mode(event.globalPosition().toPoint())
                return True

        if ball_button is not None and watched is ball_button and self.is_ball_mode:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._ball_drag_active = True
                    self._ball_drag_moved = False
                    self._ball_drag_start = event.globalPosition().toPoint()
                    self._ball_window_start = self.frameGeometry().topLeft()
                    return True

            if event.type() == QEvent.Type.MouseMove and self._ball_drag_active:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    delta = event.globalPosition().toPoint() - self._ball_drag_start
                    if delta.manhattanLength() > 2:
                        self._ball_drag_moved = True
                    self.move(self._ball_window_start + delta)
                    return True

            if event.type() == QEvent.Type.MouseButtonRelease and self._ball_drag_active:
                self._ball_drag_active = False
                if not self._ball_drag_moved:
                    self.exit_ball_mode(event.globalPosition().toPoint())
                return True

        return super().eventFilter(watched, event)

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
            STATUS_DELETED: [],
        }

        for index, todo in indexed_todos:
            if self.current_status_filter != STATUS_ALL and todo.status != self.current_status_filter:
                continue
            grouped[todo.status].append((index, todo))

        for status in STATUS_FILTER_OPTIONS:
            if status in self.hidden_statuses:
                continue

            todos_in_group = grouped[status]
            if not todos_in_group:
                continue

            collapsed = status in self.collapsed_statuses
            marker = "▸" if collapsed else "▾"
            header_item = QListWidgetItem(f"{marker} {status}（{len(todos_in_group)}）")
            header_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            header_item.setData(Qt.ItemDataRole.UserRole + 1, status)
            header_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
            self.todo_list.addItem(header_item)

            if collapsed:
                continue

            for index, todo in todos_in_group:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(8, 4, 8, 4)

                done_checkbox = QCheckBox()
                done_checkbox.setChecked(todo.done)
                done_checkbox.setEnabled(todo.status != STATUS_DELETED)
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
                if todo.status in STATUS_OPTIONS:
                    status_combo.setCurrentText(todo.status)
                else:
                    status_combo.setCurrentText(STATUS_IN_PROGRESS)
                status_combo.setEnabled(todo.status != STATUS_DELETED)
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

                row_layout.addWidget(left_widget)
                row_layout.addStretch()
                row_layout.addWidget(status_combo)

                item = QListWidgetItem(self.todo_list)
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setSizeHint(row_widget.sizeHint())
                self.todo_list.addItem(item)
                self.todo_list.setItemWidget(item, row_widget)

    def update_stats_label(self) -> None:
        in_progress_count = sum(1 for todo in self.todos if todo.status == STATUS_IN_PROGRESS)
        later_count = sum(1 for todo in self.todos if todo.status == STATUS_LATER)
        done_count = sum(1 for todo in self.todos if todo.status == STATUS_DONE)
        deleted_count = sum(1 for todo in self.todos if todo.status == STATUS_DELETED)
        self.stats_label.setText(
            f"统计：正在进行 {in_progress_count}  |  稍后进行 {later_count}  |  已完成 {done_count}  |  已删除 {deleted_count}"
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

    def open_todo_context_menu(self, position) -> None:
        item = self.todo_list.itemAt(position)
        if item is None:
            return

        index = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int):
            return
        if not (0 <= index < len(self.todos)):
            return

        menu = QMenu(self)
        todo = self.todos[index]

        if todo.status == STATUS_DELETED:
            menu.setStyleSheet(
                """
                QMenu::item:selected {
                    background-color: #16a34a;
                    color: white;
                }
                """
            )
            restore_action = QAction("恢复到正在进行", self)
            restore_action.triggered.connect(lambda: self.restore_todo(index))
            menu.addAction(restore_action)
        else:
            menu.setStyleSheet(
                """
                QMenu::item:selected {
                    background-color: #dc2626;
                    color: white;
                }
                """
            )
            delete_action = QAction("移到已删除", self)
            delete_action.triggered.connect(lambda: self.delete_todo(index))
            menu.addAction(delete_action)

        menu.exec(self.todo_list.viewport().mapToGlobal(position))

    def set_sort_mode(self, mode: str) -> None:
        self.current_sort_mode = mode
        self.refresh_list()

    def set_status_filter(self, status_filter: str) -> None:
        self.current_status_filter = status_filter
        self.refresh_list()

    def toggle_hidden_status(self, status: str, hidden: bool) -> None:
        if hidden:
            self.hidden_statuses.add(status)
        else:
            self.hidden_statuses.discard(status)
        self.refresh_list()

    def handle_list_item_clicked(self, item: QListWidgetItem) -> None:
        status = item.data(Qt.ItemDataRole.UserRole + 1)
        if not isinstance(status, str):
            return

        if status in self.collapsed_statuses:
            self.collapsed_statuses.remove(status)
        else:
            self.collapsed_statuses.add(status)
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
            self.todos[index].status = STATUS_DELETED
            self.todos[index].done = False
            self.todos[index].checked_at = None
            self.refresh_list()
            self.save_todos()

    def restore_todo(self, index: int) -> None:
        if 0 <= index < len(self.todos) and self.todos[index].status == STATUS_DELETED:
            self.todos[index].status = STATUS_IN_PROGRESS
            self.todos[index].done = False
            self.todos[index].checked_at = None
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
                            if item.get("status") in STATUS_FILTER_OPTIONS
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
                    if item.get("status") in STATUS_FILTER_OPTIONS
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

    def _normal_window_flags(self) -> Qt.WindowType:
        flags = Qt.WindowType.Window
        if self.pin_button.isChecked():
            flags |= Qt.WindowType.WindowStaysOnTopHint
        return flags

    def enter_ball_mode(self, anchor_global_pos: QPoint | None = None) -> None:
        if self.is_ball_mode:
            return

        self.is_ball_mode = True
        self.normal_geometry = self.geometry()
        collapse_center_global = (
            anchor_global_pos
            if anchor_global_pos is not None
            else self.collapse_button.mapToGlobal(self.collapse_button.rect().center())
        )
        self._collapse_anchor_offset = self.collapse_button.mapTo(self, self.collapse_button.rect().center())
        margins = self.main_layout.contentsMargins()
        self.normal_layout_margins = (margins.left(), margins.top(), margins.right(), margins.bottom())
        self.normal_layout_spacing = self.main_layout.spacing()

        self.top_bar.hide()
        self.stats_label.hide()
        self.input_row.hide()
        self.todo_list.hide()
        self.save_status_label.hide()

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        ball_flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if self.pin_button.isChecked():
            ball_flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(ball_flags)

        ball_size = 84
        visible_ball_size = 68
        inset = (ball_size - visible_ball_size) // 2
        self.setFixedSize(ball_size, ball_size)
        self.setMask(QRegion(inset, inset, visible_ball_size, visible_ball_size, QRegion.RegionType.Ellipse))
        self.main_layout.setContentsMargins(inset, inset, inset, inset)
        self.ball_button.show()
        self.show()
        self.raise_()
        self.activateWindow()
        self.ball_button.setFocus(Qt.FocusReason.OtherFocusReason)

        ball_top_left = collapse_center_global - QPoint(ball_size // 2, ball_size // 2)
        self.move(ball_top_left)
        self._align_ball_center(collapse_center_global)

    def exit_ball_mode(self, anchor_global_pos: QPoint | None = None) -> None:
        if not self.is_ball_mode:
            return

        ball_center_global = anchor_global_pos if anchor_global_pos is not None else self.mapToGlobal(self.rect().center())
        self.is_ball_mode = False
        self.ball_button.hide()

        self.top_bar.show()
        self.stats_label.show()
        self.input_row.show()
        self.todo_list.show()
        self.save_status_label.show()

        self.main_layout.setContentsMargins(*self.normal_layout_margins)
        self.main_layout.setSpacing(self.normal_layout_spacing)

        self.clearMask()
        self.setWindowFlags(self._normal_window_flags())

        self.setMinimumWidth(380)
        self.setMinimumHeight(0)
        self.setMaximumWidth(16777215)
        self.setMaximumHeight(16777215)
        if self.normal_geometry is not None:
            width = self.normal_geometry.width()
            height = self.normal_geometry.height()
            target_top_left = ball_center_global - self._collapse_anchor_offset
            self.setGeometry(target_top_left.x(), target_top_left.y(), width, height)
        self.show()
        self.raise_()
        self.activateWindow()
        self.update()
        self._align_collapse_button_center(ball_center_global)

    def _align_collapse_button_center(self, target_global_center: QPoint) -> None:
        current_center = self.collapse_button.mapToGlobal(self.collapse_button.rect().center())
        delta = target_global_center - current_center
        if delta.manhattanLength() > 0:
            self.move(self.x() + delta.x(), self.y() + delta.y())

    def _align_ball_center(self, target_global_center: QPoint) -> None:
        current_center = self.ball_button.mapToGlobal(self.ball_button.rect().center())
        delta = target_global_center - current_center
        if delta.manhattanLength() > 0:
            self.move(self.x() + delta.x(), self.y() + delta.y())

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
            status = item.get("status") if item.get("status") in STATUS_FILTER_OPTIONS else None
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
            elif status == STATUS_DELETED:
                done = False
                checked_at = None
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
            status = item.get("status") if item.get("status") in STATUS_FILTER_OPTIONS else None
            if not status:
                status = STATUS_DONE if done else STATUS_IN_PROGRESS
            if status == STATUS_DONE:
                done = True
                if not checked_at:
                    checked_at = self._now_text()
            elif status == STATUS_DELETED:
                done = False
                checked_at = None
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

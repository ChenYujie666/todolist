import os
import unittest
from unittest.mock import patch

from main import TASKBAR_SHORTCUT_COUNT, TodoApp


class ShortcutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = TodoApp.__new__(TodoApp)
        self.app.app_shortcuts = [
            {"label": f"Win+{index + 1}", "path": f"app-{index}", "icon_path": f"app-{index}"}
            for index in range(TASKBAR_SHORTCUT_COUNT)
        ]
        self.app.shortcut_open_states = [False] * TASKBAR_SHORTCUT_COUNT

    @unittest.skipUnless(os.name == "nt", "Windows-specific shortcut behavior")
    def test_buttons_map_to_windows_number_shortcuts(self) -> None:
        with patch.object(self.app, "_send_windows_number_key") as send_key:
            self.app.activate_taskbar_app(0)
            self.app.activate_taskbar_app(0)
            self.app.activate_taskbar_app(1)
            self.app.activate_taskbar_app(6)

        self.assertEqual([call.args[0] for call in send_key.call_args_list], [1, 1, 1, 2, 7])

    def test_invalid_shortcut_index_is_ignored(self) -> None:
        with patch.object(self.app, "_send_windows_number_key") as send_key:
            self.app.activate_taskbar_app(-1)
            self.app.activate_taskbar_app(TASKBAR_SHORTCUT_COUNT)

        send_key.assert_not_called()


if __name__ == "__main__":
    unittest.main()

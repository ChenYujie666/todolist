import os
import unittest
from unittest.mock import patch

from main import TodoApp

SHORTCUT_COUNT = 7


class ShortcutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = TodoApp.__new__(TodoApp)
        self.app.app_shortcuts = [
            {"label": f"Win+{index + 1}", "path": f"app-{index}", "icon_path": f"app-{index}"}
            for index in range(SHORTCUT_COUNT)
        ]
        self.app.shortcut_open_states = [False] * SHORTCUT_COUNT

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
            self.app.activate_taskbar_app(SHORTCUT_COUNT)

        send_key.assert_not_called()

    def test_taskbar_paths_preserve_registry_order(self) -> None:
        app = TodoApp.__new__(TodoApp)
        app._get_taskbar_shortcut_paths = lambda: ["first.lnk", "second.lnk"]
        paths = app._get_taskbar_shortcut_paths()
        self.assertEqual(paths, ["first.lnk", "second.lnk"])


if __name__ == "__main__":
    unittest.main()

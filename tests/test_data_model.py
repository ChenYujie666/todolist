import unittest

from main import (
    STATUS_DELETED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_LATER,
    TodoApp,
)


class TodoDataModelTests(unittest.TestCase):
    def setUp(self) -> None:
        # The parser only uses instance helpers and does not require a live Qt
        # application, so these tests stay fast and work in CI's offscreen mode.
        self.app = TodoApp.__new__(TodoApp)

    def test_parser_normalizes_legacy_and_invalid_entries(self) -> None:
        todos = self.app._todos_from_data(
            [
                {"text": "  finish report  ", "done": True},
                {"text": "later", "status": STATUS_LATER, "done": True},
                {"text": "deleted", "status": STATUS_DELETED, "done": True},
                {"text": "   "},
                "not an object",
            ]
        )

        self.assertEqual([todo.text for todo in todos], ["finish report", "later", "deleted"])
        self.assertEqual(todos[0].status, STATUS_DONE)
        self.assertTrue(todos[0].done)
        self.assertIsNotNone(todos[0].checked_at)
        self.assertEqual(todos[1].status, STATUS_LATER)
        self.assertFalse(todos[1].done)
        self.assertIsNone(todos[1].checked_at)
        self.assertEqual(todos[2].status, STATUS_DELETED)
        self.assertFalse(todos[2].done)

    def test_parser_rejects_non_array_data(self) -> None:
        with self.assertRaises(ValueError):
            self.app._todos_from_data({"text": "one"})

    def test_unknown_status_falls_back_to_done_or_in_progress(self) -> None:
        todos = self.app._todos_from_data(
            [
                {"text": "done", "done": True, "status": "unknown"},
                {"text": "open", "done": False, "status": "unknown"},
            ]
        )

        self.assertEqual(todos[0].status, STATUS_DONE)
        self.assertEqual(todos[1].status, STATUS_IN_PROGRESS)


if __name__ == "__main__":
    unittest.main()

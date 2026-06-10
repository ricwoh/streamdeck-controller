"""Aktions-Bibliothek und Executor."""

from streamdeck_controller.actions import ACTION_LIBRARY, ACTIONS_BY_ID, ActionExecutor
from streamdeck_controller.paths import resolve_icon


def test_library_ids_unique():
    ids = [a.id for a in ACTION_LIBRARY]
    assert len(ids) == len(set(ids))


def test_every_action_has_builtin_icons():
    for spec in ACTION_LIBRARY:
        assert resolve_icon(spec.icon) is not None, f"Icon fehlt: {spec.icon}"
        assert resolve_icon(spec.icon_active) is not None, f"Icon fehlt: {spec.icon_active}"


def test_executor_handles_every_library_action():
    executor = ActionExecutor(ctx=None)
    for spec in ACTION_LIBRARY:
        assert hasattr(executor, f"_do_{spec.id}"), f"Kein Handler für {spec.id}"


class _Ctx:
    spotify = None

    def __init__(self):
        self.calls = []

    def goto_page(self, idx):
        self.calls.append(("goto", idx))

    def next_page(self):
        self.calls.append(("next",))

    def prev_page(self):
        self.calls.append(("prev",))


def test_page_actions():
    ctx = _Ctx()
    executor = ActionExecutor(ctx)
    executor.execute({"id": "page_goto", "params": {"page": 3}})
    executor.execute({"id": "page_next", "params": {}})
    executor.execute({"id": "page_prev", "params": {}})
    assert ctx.calls == [("goto", 2), ("next",), ("prev",)]


def test_unknown_action_is_safe():
    executor = ActionExecutor(_Ctx())
    executor.execute({"id": "gibt_es_nicht", "params": {}})
    executor.execute({})
    executor.execute(None)


def test_spotify_action_without_login_does_not_crash():
    ctx = _Ctx()  # spotify = None
    executor = ActionExecutor(ctx)
    executor.execute({"id": "spotify_play_pause", "params": {}})


def test_empty_command_params_do_nothing():
    executor = ActionExecutor(_Ctx())
    executor.execute({"id": "custom_cmd", "params": {"cmd": ""}})
    executor.execute({"id": "app_launch", "params": {}})

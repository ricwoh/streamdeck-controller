from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamdeck_app.py"


def _class_node(name: str) -> ast.ClassDef:
    tree = ast.parse(APP.read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _self_default_assignments(func: ast.FunctionDef) -> dict[str, int]:
    values: dict[str, int] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            # self._cols = 3
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr in {"_cols", "_rows"}
            ):
                values[target.attr] = ast.literal_eval(node.value)
            # self._cols, self._rows = 3, 2
            elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for left, right in zip(target.elts, node.value.elts):
                    if (
                        isinstance(left, ast.Attribute)
                        and isinstance(left.value, ast.Name)
                        and left.value.id == "self"
                    ):
                        values[left.attr] = ast.literal_eval(right)
    return values


def test_streamdeck_window_defaults_to_mini_grid_3_by_2():
    window_class = _class_node("StreamDeckWindow")
    init_func = next(
        node for node in window_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )

    assignments = _self_default_assignments(init_func)

    assert assignments["_cols"] == 3
    assert assignments["_rows"] == 2

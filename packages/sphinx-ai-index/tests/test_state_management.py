"""State Management property tests and deterministic tests.

These tests ensure the WeakKeyDictionary isolates builds properly.
"""

from typing import Any

from docutils import utils

from sphinx_ai_index import (
    _build_data,
    on_build_finished,
    on_builder_inited,
    on_doctree_resolved,
)


class MockBuilder:
    def __init__(self, name: str):
        self.name = name


class MockApp:
    def __init__(self, builder_name: str):
        self.builder = MockBuilder(builder_name)
        self.env = object()


def test_build_data_isolation() -> None:
    """Ensure that multiple App instances get entirely separate state dictionaries."""
    app1 = MockApp("html")
    app2 = MockApp("html")
    app3 = MockApp("text")

    # Cast mocks to Sphinx to satisfy the function signatures
    on_builder_inited(app1)  # type: ignore[arg-type]
    on_builder_inited(app2)  # type: ignore[arg-type]
    on_builder_inited(app3)  # type: ignore[arg-type]

    # text builder should not have initialized dict
    assert app3 not in _build_data  # type: ignore[arg-type]

    # html builders should have independent dicts
    assert app1 in _build_data  # type: ignore[arg-type]
    assert app2 in _build_data  # type: ignore[arg-type]

    data1: dict[str, Any] = _build_data[app1]  # type: ignore[arg-type]

    # Mutating one doesn't mutate another
    data1["test_doc"] = {"title": "Doc 1"}

    assert "test_doc" in _build_data[app1]  # type: ignore[arg-type]
    assert "test_doc" not in _build_data[app2]  # type: ignore[arg-type]


def test_build_data_garbage_collection() -> None:
    """Ensure that when an App instance goes out of scope, its state is cleaned up."""
    # Ensure a clean start to our check
    initial_length = len(_build_data)

    app_target = MockApp("html")
    on_builder_inited(app_target)  # type: ignore[arg-type]

    assert len(_build_data) == initial_length + 1

    # Delete the app reference
    del app_target

    # Because _build_data is a WeakKeyDictionary, deleting the key should remove the item
    assert len(_build_data) == initial_length


def test_on_doctree_resolved_no_pagedata() -> None:
    app = MockApp("html")
    doctree = utils.new_document("test")
    on_doctree_resolved(app, doctree, "testdoc")  # type: ignore[arg-type]


def test_on_build_finished_with_exception() -> None:
    app = MockApp("html")
    on_builder_inited(app)  # type: ignore[arg-type]
    on_build_finished(app, Exception("Something went wrong"))  # type: ignore[arg-type]


def test_on_build_finished_no_pagedata() -> None:
    app = MockApp("html")
    on_build_finished(app, None)  # type: ignore[arg-type]

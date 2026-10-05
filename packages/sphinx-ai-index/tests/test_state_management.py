"""State Management unit tests.

These tests ensure the new _get_index_data isolates builds properly based on the environment.
"""

from sphinx_ai_index import (
    _get_index_data,
    on_build_finished,
    on_env_merge_info,
    on_env_purge_doc,
)


class MockBuilder:
    def __init__(self, name: str):
        self.name = name
        self.format = name


class MockEnv:
    def __init__(self):
        pass


class MockApp:
    def __init__(self, builder_name: str):
        self.builder = MockBuilder(builder_name)
        self.env = MockEnv()


def test_build_data_isolation() -> None:
    """Ensure that multiple environments get entirely separate stat dictionaries."""
    env1 = MockEnv()
    env2 = MockEnv()

    data1 = _get_index_data(env1)
    _get_index_data(env2)

    # Mutating one doesn't mutate another
    data1["test_doc"] = {"title": "Doc 1"}

    assert "test_doc" in _get_index_data(env1)
    assert "test_doc" not in _get_index_data(env2)


def test_on_env_purge_doc() -> None:
    app = MockApp("html")
    env = MockEnv()
    data = _get_index_data(env)
    data["testdoc"] = {"title": "Test Doc"}

    assert "testdoc" in _get_index_data(env)
    on_env_purge_doc(app, env, "testdoc")
    assert "testdoc" not in _get_index_data(env)


def test_on_env_merge_info() -> None:
    app = MockApp("html")
    env_main = MockEnv()
    env_worker = MockEnv()

    data_main = _get_index_data(env_main)
    data_worker = _get_index_data(env_worker)

    data_worker["worker_doc"] = {"title": "Worker Doc"}

    assert "worker_doc" not in data_main
    on_env_merge_info(app, env_main, ["worker_doc"], env_worker)
    assert "worker_doc" in data_main
    assert data_main["worker_doc"]["title"] == "Worker Doc"


def test_on_build_finished_with_exception() -> None:
    app = MockApp("html")
    on_build_finished(app, Exception("Something went wrong"))


def test_on_build_finished_no_pagedata() -> None:
    app = MockApp("html")
    on_build_finished(app, None)

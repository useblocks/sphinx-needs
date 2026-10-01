"""ub-test-reports' suite needs no Sphinx: only pytest's own ``pytester``.

It runs in the default environment and, in CI's ``toolchain-free`` and ``plugin-floor``
jobs, against the BUILT wheel in an environment where Sphinx, sphinx-needs and docutils are
absent -- so nothing here may import them, and the fixtures it reads are this package's own
copies under ``tests/fixtures/``.
"""

pytest_plugins = ["pytester"]

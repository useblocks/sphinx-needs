"""libclang-based, preprocessor-aware extraction engine (opt-in)."""

from sphinx_codelinks.analyse.preproc import compile_db, libclang_parser, loader

__all__ = ["compile_db", "libclang_parser", "loader"]

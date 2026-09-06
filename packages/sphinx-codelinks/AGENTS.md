# AGENTS.md — packages/sphinx-codelinks

The delta for this package. Everything repository-level — the workspace layout, the
commands, the lock, lint/format/type-check configuration, the release recipe, the pull
request requirements and the commit-message convention — is in the ROOT
[`AGENTS.md`](../../AGENTS.md), and this file does not repeat it. What is here is what an
agent has to know that is true of sphinx-codelinks and not of the workspace.

## Project Overview

sphinx-codelinks is a Sphinx extension that provides fast source code traceability for
sphinx-needs. It:

- **analyses source code** — scans C, C++, C#, Python, Rust, Go, YAML, JSON and Bash files
  for special comment markers, with tree-sitter;
- **creates needs from them** — turns discovered markers into sphinx-needs items;
- **traces sources** — links documentation to exact source lines, and generates a
  syntax-highlighted HTML page per traced file with line anchors;
- **has a CLI** — `codelinks analyse` and `codelinks write`, for use outside a Sphinx build.

It is the only member of this workspace whose `src/` imports `sphinx_needs`, and it
declares it as a **runtime** dependency with a tight floor (`sphinx-needs>=8.5.0,<9`,
which `check_workspace.py` check (4) enforces against the sibling's current version, and
`propagate_floors.py` moves at each sphinx-needs release).

## Package structure

```text
pyproject.toml          # `[project]`, `[project.urls]`, `[build-system]` and nothing else:
                        #   ruff, ty, pytest and the dependency groups are the ROOT's
.readthedocs.yaml       # this package's RTD project; every path in it is relative to the
                        #   REPOSITORY root, not to the file
README.md · LICENSE
design/                 # import-commit-map.txt: old hash -> new hash for the 2026-09 import

src/sphinx_codelinks/   # Main source code
├── __init__.py         # `__version__` (public, in `__all__`) and the Sphinx `setup()`
├── cmd.py              # CLI commands using Typer
├── config.py           # Configuration models using Pydantic
├── logger.py           # Logging utilities
├── needextend_write.py # Write RST files with Sphinx-Needs directives
├── analyse/            # Code analysis module
│   ├── analyse.py      # Main analysis orchestration
│   ├── models.py       # Pydantic models for analysis results
│   ├── oneline_parser.py # One-line comment parser
│   ├── projects.py     # Project-specific analyzers (C++, Python, etc.)
│   ├── utils.py        # Analysis utilities, including the git-root helpers
│   └── preproc/        # the OPTIONAL libclang engine -- see below
├── source_discover/    # Source file discovery
│   ├── config.py       # Discovery configuration
│   └── source_discover.py # File discovery logic
└── sphinx_extension/   # Sphinx extension components
    ├── source_tracing.py # Main Sphinx extension setup
    ├── html_wrapper.py  # HTML output wrapper for traced source
    ├── debug.py         # Debug utilities
    ├── ub_sct.css       # CSS for source tracing UI
    └── directives/      # Custom Sphinx directives

tests/                  # Test suite -- `tests/__init__.py` is why this path is NOT in the
├── __init__.py         #   root `testpaths` (see the root AGENTS.md)
├── conftest.py         # Pytest fixtures and configuration
├── test_*.py           # 18 test modules
├── __snapshots__/      # Syrupy snapshot test fixtures
├── data/               # Test data and fixtures
└── doc_test/           # minimal Sphinx projects for the integration tests

docs/                   # Documentation source (RST) -- conf.py sits IN the source dir,
├── conf.py             #   so `sphinx-build docs docs/_build/html` needs no `-c`
├── ubproject.toml      # this docs project's own needs + codelinks configuration
├── changelog.rst       # `bump.py` stamps this path; do not move it
├── index.rst · basics/ · components/ · development/ · _static/
```

## The two facts that are workspace-specific

### libclang is optional, and 56 tests depend on it

The preprocessor-aware C/C++ engine (`analyse/preproc/`) needs `clang.cindex`, which comes
from the `libclang` wheel. It is optional at runtime — the member's `libclang` extra — and
`analyse/preproc/__init__.py` imports the loader **eagerly**, so importing anything under
that package without the wheel raises.

In this workspace the wheel is the root dependency group **`codelinks-libclang`**, not part
of `test`: it is 23 MiB and 81 MB on disk, and every cell of every package would otherwise
pay for it. Every `test-codelinks*` poe task adds the group, and so does CI's Extensions
cell.

```bash
uv run poe test-codelinks                       # 357 passed
uv run --frozen --no-sync pytest packages/sphinx-codelinks/tests   # 301 passed, 26 skipped
```

**Both are green, and only one of them tested the engine.** The four modules that need it
carry `pytest.importorskip("clang.cindex")`, so a run without the group skips politely
rather than failing — which means a task or a CI line that quietly lost the group would
look like a pass. If you are changing anything under `analyse/preproc/`, check the number.

### This package caps `click` and `typer`, and nothing else in the lock does

`click < 8.2` (8.2 produces empty errors when the CLI is given no arguments) and
`typer >=0.16.0,<0.26.8` (0.26.8 removed `rich_utils.STYLE_METAVAR`, which
`sphinxcontrib-typer` still imports for the docs build). Measured across every
`requires-dist` in `uv.lock`: **no other package in this workspace names `click`, `typer`,
`rich` or `shellingham` at all**, so the caps constrain nothing but this package today.
The direction to watch is the reverse one — the day a root, `test` or `dev` dependency
wants `click>=8.2`, `uv lock` will fail and the reason will be here.

## Documentation

`uv run poe docs-codelinks` (and `docs-codelinks-clean`). `-nW --keep-going`, no renderer:
these docs draw no diagrams, so unlike `docs-needs` there is no `dot`, `java` or plantuml
to install. They DO need two things a normal checkout has and a stripped one may not:

- **a git remote and a readable git directory.** `src-trace` turns every traced source line
  into a blob link at the current rev, read out of the git directory's `config` and `HEAD`.
  Worktrees are handled (`_git_dir` / `_git_common_dir` in `analyse/utils.py`); a checkout
  with no `origin` is not, and the build fails under `-nW` with five
  `[codelinks.git_remote]` warnings.
- **network for intersphinx** to `sphinx-needs.readthedocs.io` and `www.sphinx-doc.org`.

These docs are the one end-to-end exercise of the extension — `src-trace` runs over four
projects of this package's own source — which is why CI builds them on every pull request
(`Docs codelinks` in `ci.yaml`).

## Code Style Guidelines

Formatting, linting and type checking are the ROOT's — one ruff configuration, one ty
configuration, one prek config (`uv run poe lint`, `uv run poe typecheck`). The root's
`[tool.ruff.lint.per-file-ignores]` carries this package's one entry
(`packages/sphinx-codelinks/tests/*`: `E402` for the `importorskip` guard pattern, `SIM300`
for a deliberate assert order). What is specific to this package:

- **Type annotations**: complete annotations on every function signature. Pydantic models
  for configuration and data structures.
- **Docstrings**: Sphinx-style (`:param:`, `:return:`, `:raises:`). No types in the
  docstring — they belong in the annotations.
- **Immutability**: prefer immutable structures; frozen Pydantic models for configuration.
- **Pure functions** where possible.
- **Error handling**: descriptive exceptions, custom types where they help.

### Docstring Example

```python
def discover_source_files(
    root_dir: Path,
    include_patterns: list[str],
    exclude_patterns: list[str],
    *,
    respect_gitignore: bool = True,
) -> list[Path]:
    """Discover source files matching the given patterns.

    :param root_dir: The root directory to search from.
    :param include_patterns: Glob patterns for files to include.
    :param exclude_patterns: Glob patterns for files to exclude.
    :param respect_gitignore: Whether to respect .gitignore rules.
    :return: List of discovered file paths.
    :raises ValueError: If root_dir does not exist.
    """
    ...
```

## Testing Guidelines

`uv run poe test-codelinks` (trailing arguments go to pytest), and
`test-codelinks-sphinx7/8/9` for one matrix cell each. Snapshots:
`uv run poe test-codelinks -- --snapshot-update`.

### Test Structure

- Tests use `pytest` with fixtures from `conftest.py`
- Snapshot testing uses `syrupy` for complex output comparisons
- Test data is in `tests/data/`
- Sphinx integration tests use real Sphinx projects in `tests/doc_test/`
- `tests/test_analyse_utils.py` builds real `git init` repositories and a real
  `git worktree`, so `git` must be on PATH

### Writing Tests

1. For code analysis tests, create test data in `tests/data/` with source files
2. Use `syrupy` for comparing complex analysis outputs (JSON, doctrees, etc.)
3. For Sphinx integration, create minimal projects in `tests/doc_test/`
4. Use parametrized tests for testing multiple language parsers

### Test Best Practices

- **Test coverage**: write tests for all new functionality and bug fixes
- **Isolation**: each test independent of every other's state
- **Descriptive names**: the function name says what is tested
- **Snapshot testing**: `assert snapshot == result` for complex outputs
- **Parametrization**: `@pytest.mark.parametrize` for multiple scenarios
- **Fixtures**: reusable ones in `conftest.py`
- **No CWD assumptions.** The suite must pass both from `packages/sphinx-codelinks` and
  from the repository root, because CI runs it from the root. A test that resolves a
  relative path against the CWD passes in one and fails in the other — that was
  `test_form_https_url` until the import fixed it.

### Example Test Pattern

```python
import pytest
from pathlib import Path

def test_analyse_cpp_file(snapshot, tmp_path):
    """Test C++ file analysis produces correct output."""
    # Arrange
    source_file = tmp_path / "test.cpp"
    source_file.write_text("""
    // @req{REQ-001}
    void function() {}
    """)

    # Act
    result = analyse_file(source_file)

    # Assert
    assert snapshot == result
```

## Architecture Overview

### Analysis Pipeline

The code analysis follows a multi-stage pipeline:

```text
Source Files → Discovery → Parsing → Analysis → Results (JSON) → RST Generation
```

1. **Discovery** (`source_discover/`): Scan directories for source files matching patterns
2. **Parsing** (`analyse/oneline_parser.py`): Use tree-sitter to parse source code AST
3. **Analysis** (`analyse/analyse.py`, `analyse/projects.py`): Extract markers and metadata
4. **Output** (`needextend_write.py`): Generate RST with Sphinx-Needs directives

### Sphinx Integration Flow

The Sphinx extension hooks into multiple build events to provide source tracing:

```mermaid
flowchart TB
    subgraph init["Initialization (config-inited)"]
        setup["setup() in __init__.py"]
        load_toml["load_config_from_toml()"]
        sn_options["update_sn_extra_options()"]
        sn_types["update_sn_types()"]
        check_config["check_sphinx_configuration()"]
    end

    subgraph prepare["Build Preparation"]
        builder_init["builder_inited: Copy CSS assets"]
        env_prepare["env-before-read-docs: prepare_env()"]
    end

    subgraph generate["Page Generation (html-collect-pages)"]
        gen_pages["generate_code_page()"]
        html_wrap["html_wrapper()"]
    end

    subgraph context["Page Context (html-page-context)"]
        add_css["add_custom_css()"]
    end

    subgraph finish["Build Finished"]
        warnings["emit_warnings()"]
        timing["debug.process_timing()"]
    end

    setup --> load_toml --> sn_options --> sn_types --> check_config
    check_config --> builder_init --> env_prepare
    env_prepare --> gen_pages --> html_wrap
    html_wrap --> add_css --> warnings --> timing

    style load_toml fill:#e1f5fe
    style gen_pages fill:#e1f5fe
    style html_wrap fill:#e1f5fe
```

#### Event Handlers

The extension connects to these Sphinx events (in execution order):

| Event                  | Handler                        | Purpose                                                              |
| ---------------------- | ------------------------------ | -------------------------------------------------------------------- |
| `config-inited`        | `load_config_from_toml()`      | Load configuration from TOML file if specified                       |
| `config-inited`        | `update_sn_extra_options()`    | Register sphinx-needs extra options (project, file, directory, URLs) |
| `config-inited`        | `update_sn_types()`            | Add `srctrace` need type to sphinx-needs                             |
| `config-inited`        | `check_sphinx_configuration()` | Validate configuration and raise errors                              |
| `builder-inited`       | `builder_inited()`             | Copy CSS assets to output directory                                  |
| `env-before-read-docs` | `prepare_env()`                | Initialize timing measurements and debug filters                     |
| `html-collect-pages`   | `generate_code_page()`         | Generate HTML pages for traced source files                          |
| `html-page-context`    | `add_custom_css()`             | Inject custom CSS for source tracing UI                              |
| `build-finished`       | `emit_warnings()`              | Emit collected warnings from analysis                                |
| `build-finished`       | `debug.process_timing()`       | Output timing measurements if enabled                                |

#### Key Integration Points

1. **sphinx-needs Dependency**: The extension requires sphinx-needs and checks for its presence in `setup()`. It adds extra options (`project`, `file`, `directory`, URL fields) and a custom need type (`srctrace`).

2. **TOML Configuration**: Configuration can be loaded from a TOML file specified in `conf.py` via `src_trace_config_from_toml`. The TOML is parsed and values are set on the Sphinx config object.

3. **Source Page Generation**: The `generate_code_page()` function yields tuples of `(pagename, context, template)` for each traced source file, allowing Sphinx to generate standalone HTML pages with syntax-highlighted source code and line-number anchors.

4. **CSS Injection**: Custom CSS (`ub_sct.css`) is copied to `_static/source_tracing/` and added only to pages that contain traced source code.

### Key Components

#### Configuration (`config.py`)

Pydantic models define all configuration options:

- `AnalyseConfig`: Main analysis configuration with source paths, patterns, markers
- Uses Pydantic v2 with validation and serialization
- Configuration loaded from TOML files

#### Source Discovery (`source_discover/`)

- `discover_source_files()`: Find source files matching include/exclude patterns
- Respects `.gitignore` rules using `gitignore-parser`
- Returns filtered list of files to analyze

#### Code Analysis (`analyse/`)

- **`analyse.py`**: Main orchestrator that coordinates analysis across all source files
- **`projects.py`**: Language-specific analyzers (C++, Python, C#, Rust, YAML)
- **`oneline_parser.py`**: Tree-sitter based parser for extracting comment markers
- **`models.py`**: Pydantic models for analysis results (markers, line ranges, etc.)
- **`utils.py`**: Helper functions for path handling, marker extraction

#### Tree-sitter Integration

- Uses tree-sitter parsers for each supported language
- Extracts comments from AST nodes
- Parses special marker syntax (e.g., `@req{ID}`, `@test{ID}`)
- Maintains line number information for source tracing

#### Sphinx Extension (`sphinx_extension/`)

- **`source_tracing.py`**: Main extension setup with `setup()` function
- **`html_wrapper.py`**: Wraps source code blocks with tracing metadata
- **`debug.py`**: Debug utilities for development
- Hooks into Sphinx build events to inject source tracing information

### CLI Interface

The CLI uses Typer for command definitions:

- `codelinks analyse <config>`: Analyze source code and output JSON
- `codelinks write <format> <input> --outpath <file>`: Generate RST from JSON

## Key Files

- `pyproject.toml` - Project configuration, dependencies, and tool settings
- `src/sphinx_codelinks/__init__.py` - Package entry point with `setup()` for Sphinx
- `src/sphinx_codelinks/cmd.py` - CLI commands and argument parsing
- `src/sphinx_codelinks/config.py` - Pydantic configuration models
- `src/sphinx_codelinks/analyse/analyse.py` - Main analysis orchestration
- `src/sphinx_codelinks/analyse/projects.py` - Language-specific analyzers
- `src/sphinx_codelinks/analyse/oneline_parser.py` - Tree-sitter comment parser
- `src/sphinx_codelinks/sphinx_extension/source_tracing.py` - Sphinx extension setup
- `tests/conftest.py` - Pytest fixtures and test configuration

## Debugging

- `uv run poe test-codelinks -- --pdb` drops into the debugger on a failure
- `-v` for verbose output, `--log-cli-level=DEBUG` for logging
- the docs task already passes `-T`, so a docs failure prints a full traceback
- `sphinx_extension/debug.py` holds the development helpers (`measure_time`, the timing
  report emitted on `build-finished`)

## Common Patterns

### Adding Support for a New Language

1. Add tree-sitter parser dependency to `pyproject.toml` (e.g., `tree-sitter-java`)
2. Create language-specific analyzer in `analyse/projects.py`:

   ```python
   class JavaAnalyzer(BaseAnalyzer):
       language = "java"
       parser_language = "java"

       def get_comment_nodes(self, tree):
           # Return comment nodes from tree
   ```

3. Register analyzer in `LANGUAGE_ANALYZERS` dict in `projects.py`
4. Add test files in `tests/data/<language>/`
5. Add tests in `tests/test_analyse.py`

### Adding a New Marker Type

1. Update marker regex patterns in `config.py` or analyzer
2. Update `models.py` if new fields are needed
3. Update parsing logic in `oneline_parser.py`
4. Update RST generation in `needextend_write.py` if needed
5. Add tests with new marker examples

### Adding a CLI Command

1. Add command function in `cmd.py` using Typer decorators:

   ```python
   @app.command()
   def new_command(arg: str = typer.Argument(..., help="Description")):
       """Command description."""
       # Implementation
   ```

2. Add tests in `tests/test_cmd.py`
3. Update documentation in `docs/components/cli.rst`

### Adding Configuration Options

1. Add field to `AnalyseConfig` or relevant Pydantic model in `config.py`
2. Add validation if needed using Pydantic validators
3. Update TOML configuration examples in `docs/` and `tests/data/configs/`
4. Add tests for new configuration option
5. Document in `docs/components/configuration.rst`

## Reference Documentation

- [Sphinx Documentation](https://www.sphinx-doc.org/) · [Repository](https://github.com/sphinx-doc/sphinx)
- [Sphinx-Needs Documentation](https://sphinx-needs.readthedocs.io/) · [Repository](https://github.com/useblocks/sphinx-needs)
- [tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/) · [Repository](https://github.com/tree-sitter/tree-sitter)
- [Pydantic Documentation](https://docs.pydantic.dev/) · [Repository](https://github.com/pydantic/pydantic)
- [pytest Documentation](https://docs.pytest.org/) · [Repository](https://github.com/pytest-dev/pytest)
- [Typer Documentation](https://typer.tiangolo.com/) · [Repository](https://github.com/fastapi/typer)

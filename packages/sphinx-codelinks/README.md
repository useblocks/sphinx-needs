# Sphinx CodeLinks

A Sphinx extension for discovering, linking, and documenting source code across projects.

## Features

- **Source Discovery**: Automatically discover source files in your project
- **Analyse**: Parse source codes and extract specified markers with their metadata
- **Code Linking**: Create intelligent links between code elements
- **Sphinx Integration**: Seamless integration with existing Sphinx documentation

## Quick Start

```bash
pip install sphinx-codelinks
```

Add to your `conf.py`:

```python
extensions = ['sphinx_needs', 'sphinx_codelinks']
src_trace_config_from_toml = "codelinks.toml"
```

## Documentation

Full documentation: https://codelinks.useblocks.com

## Components

- **Source Discovery** ([`src/sphinx_codelinks/source_discover`](src/sphinx_codelinks/source_discover)): Code analysis and discovery
- **Analyse** ([`src/sphinx_codelinks/analyse`](src/sphinx_codelinks/analyse)): Documentation generation
- **Sphinx Extension** ([`src/sphinx_codelinks/sphinx_extension`](src/sphinx_codelinks/sphinx_extension)): Sphinx integration
- **Command Line** ([`src/sphinx_codelinks/cmd.py`](src/sphinx_codelinks/cmd.py)): CLI interface

## Development

See [Development Guide](docs/source/development/) for contributing guidelines.

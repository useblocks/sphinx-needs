# Sphinx CodeLinks

A Sphinx extension for discovering, linking, and documenting source code across projects.

## Features

- **Source Discovery**: Automatically discover source files in your project
- **Virtual Documentation**: Generate documentation from code without modifying source files
- **Code Linking**: Create intelligent links between code elements
- **Sphinx Integration**: Seamless integration with existing Sphinx documentation

## Quick Start

```bash
pip install sphinx-codelinks
```

Add to your `conf.py`:

```python
extensions = ['sphinx_needs', 'sphinx_codelinks']
```

## Documentation

Full documentation: https://codelinks.useblocks.com

## Components

- **Source Discovery** ([`src/sphinx_codelinks/source_discovery`](src/sphinx_codelinks/source_discovery)): Code analysis and discovery
- **Virtual Docs** ([`src/sphinx_codelinks/virtual_docs`](src/sphinx_codelinks/virtual_docs)): Documentation generation
- **Sphinx Extension** ([`src/sphinx_codelinks/sphinx_extension`](src/sphinx_codelinks/sphinx_extension)): Sphinx integration
- **Command Line** ([`src/sphinx_codelinks/cmd.py`](src/sphinx_codelinks/cmd.py)): CLI interface

## Development

See [Development Guide](docs/source/development/) for contributing guidelines.

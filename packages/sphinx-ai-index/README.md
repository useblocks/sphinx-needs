# sphinx-ai-index

A Sphinx extension that generates an AI-readable documentation index (`ai_docs_index.json`) in the HTML output directory on every build.

## Installation

Install from PyPI:

```bash
pip install sphinx-ai-index
```

Or add it to your `pyproject.toml`:

```toml
dependencies = [
    "sphinx-ai-index",
]
```

## Compatibility

- **Python 3.9 and newer** are supported.
- **Sphinx 5–9** are supported on Python 3.9–3.12.
- **Sphinx 6–9** are supported on Python 3.13 and 3.14.

## Usage

Add the extension to your Sphinx `conf.py`:

```python
extensions = ["sphinx_ai_index"]
```

That's it. On the next HTML build, `ai_docs_index.json` will appear in the output directory.

### `.. page-summary::` directive

Optionally annotate any RST page with a short prose description:

```rst
.. page-summary::

    This page covers the installation of the package on all major platforms,
    including system requirements and VS Code extension setup.
```

Pages without the directive are still indexed; their `summary` field will be an empty string.

## Output format

`ai_docs_index.json` is written to the HTML output directory:

```json
{
  "version": "1.0",
  "pages": [
    {
      "rst_source_path": "_sources/basics/installation.rst.txt",
      "html_path": "basics/installation.html",
      "title": "Installation",
      "sections": ["System Requirements", "Installing via pip"],
      "summary": "Covers installation on all platforms."
    }
  ]
}
```

| Field | Description |
|---|---|
| `rst_source_path` | Path to the RST source in the HTML output (under `_sources/`) |
| `html_path` | Path to the rendered HTML page, relative to the output root |
| `title` | Page title |
| `sections` | Titles of the top-level subsections within the page |
| `summary` | Text from the `.. page-summary::` directive, or `""` |

## Development

```bash
git clone https://github.com/useblocks/sphinx-ai-index.git
cd sphinx-ai-index
rye sync
rye run tox
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

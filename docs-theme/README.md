# docs-theme

The useblocks look for [furo](https://pradyunsg.me/furo/), in ONE place for every furo
documentation site in this repository: sphinx-needs (when `DOCS_THEME=furo`, which is what
Read the Docs builds), sphinx-codelinks and sphinx-mounts.

| file | what it is |
|---|---|
| `ub_docs_theme.py` | a local Sphinx extension. Under furo it adds the two directories below, the sidebar (furo's own plus the source-repository link), the `view`/`edit` buttons and the repository the buttons point into; under any other theme it does nothing |
| `static/ub-furo.css` | the brand colours mapped onto furo's tokens, light and dark; sphinx-design's tokens; the `--sn-color-*` tokens sphinx-needs draws its needs and tables with; the sidebar and source-link rules |
| `templates/side-github.html` | the source-repository link in the left sidebar |

## How a site loads it

```python
_DOCS_THEME = Path(__file__).resolve().parents[3] / "docs-theme"
if _DOCS_THEME.is_dir():
    sys.path.insert(0, str(_DOCS_THEME))
    extensions.append("ub_docs_theme")

html_theme = "furo"
html_theme_options = {
    "source_directory": "packages/<distribution>/docs/",
    "light_logo": "...",
    "dark_logo": "...",
}
```

Everything the extension sets is a default: a value the site's `conf.py` gives wins
(`html_sidebars`, `html_context["repository"]`, and each of `sidebar_hide_name`,
`top_of_page_buttons`, `source_repository` and `source_branch` separately). `ub-furo.css`
loads at priority 700: after furo's own `styles/furo-extensions.css` (600), whose
sphinx-design tokens it overrides, and before the site's own `html_css_files` (800), so a
rule only one site needs goes in that site's stylesheet and overrides the shared one. A template or a
static file of the site's own with the same name wins over the shared one: the extension
puts the shared `static/` FIRST in `html_static_path` (Sphinx copies the entries in order,
each over the last) and the shared `templates/` LAST in `templates_path` (Sphinx takes the
first match).

## Why it is a directory and not a package

It is about 300 lines of CSS and a template, and nothing outside this repository uses it. A
package would be a PyPI project with its own releases, and every docs extra would be
tight-tracked to it (`check_workspace.py`), so a colour change would be a release of its own
and a floor raise in every docs extra.
A directory costs three things instead, and each is handled where it bites:

- **An sdist does not carry it.** sphinx-needs' sdist ships `docs/` and nothing above its own
  directory, so each `conf.py` loads the extension only when the directory exists; a docs
  build from an sdist falls back to plain furo, and sphinx-needs' `installation.rst`, which
  literalincludes the `--sn-color-*` block from `ub-furo.css`, warns that it cannot find it.
- **Read the Docs skips pull-request builds by path.** The `post_checkout` filter of every
  project whose site loads it names `docs-theme/`, so a change here rebuilds each preview.
- **Pull requests are labelled by path.** `.github/labeler.yml` lists `docs-theme/**` under
  `pkg: workspace`.

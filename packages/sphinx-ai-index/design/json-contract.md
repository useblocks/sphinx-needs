# `ai_docs_index.json` — the contract

sphinx-ai-index writes one file, `ai_docs_index.json`, and its reader of record is ubCode:
the `ubc_docs` crate fetches it from a published documentation site and turns it into the
page catalog its documentation search answers from. This file pins what the producer
writes and what that consumer does with it, so that a change on either side is a change
to a written contract rather than a surprise on the other.

The producer is `src/sphinx_ai_index/__init__.py` (`on_build_finished`, and the
`on_doctree_read` data it collects). The consumer was read at ubCode `origin/main`
`ab980c2d3e87af87264b7d5465471a03d5efa8c9` (2026-10-05): `rust/ubc_docs/src/catalog.rs`
(`RawAiIndex`, `RawAiPage`, `pages_from_ai_index`, `docname_from_rst_source_path`,
`SourceCatalog::new`, `MAX_CATALOG_PAGES`), `rust/ubc_docs/src/service.rs` (`AI_INDEX_MAX_BYTES`,
`fill_source`, `DocsService::page`), `rust/ubc_docs/src/index.rs` (`page_for_rst_path`),
`rust/ubc_docs/src/sources.rs` (`join_url`, `is_safe_site_path`) and the crate documentation in
`rust/ubc_docs/src/lib.rs`.

## When the file is written

At `build-finished`, into the builder's output directory, and only when all three hold:
the build raised no exception; the builder's `format` is `"html"` — which is `html`,
`dirhtml` and `singlehtml`, and also `epub`, `json` and `pickle`; never `text`, `latex`,
`linkcheck`, …; and the build environment holds page data for at least one document. The
data lives on the (pickled) environment, so an incremental rebuild that reads no document
("0 added, 0 changed, 0 removed") still writes the file, from the data of earlier reads. It
is UTF-8, `json.dumps(…, indent=2, ensure_ascii=False)`, with a trailing newline.

## The document

```json
{"version": "1.0", "pages": [ { …page… }, … ]}
```

| field | producer | consumer |
|---|---|---|
| `version` | always the string `"1.0"` — the format's version, not the package's | **not read** (deliberately not modelled: nothing branches on it) |
| `pages` | one entry per document in the build environment, in the environment's order (read order; with parallel reads, the order the workers' data was merged in) — not sorted | `#[serde(default)]`: a missing list is an empty catalog |

Unknown top-level and page fields are ignored by the consumer (serde's default), so a
field may be **added** without breaking a deployed reader. Removing or renaming one of the
five below is a breaking change on the consumer's side even though it would still parse:
every field is `#[serde(default)]`, so it would silently read as empty. `#[serde(default)]`
covers a MISSING field only: a `null` or a wrong-typed value in any page field fails the
parse of the WHOLE file (`serde_json::from_slice`), and the source falls back to its
`objects.inv`.

## A page

Every page carries exactly these five fields, every one always present.

| field | producer rule | consumer rule |
|---|---|---|
| `rst_source_path` | `_sources/<docname><source suffix><html_sourcelink_suffix>` — e.g. `_sources/guide/install.rst.txt` — with the link suffix not appended twice when the source path already ends in it; **`""` for every page when `html_copy_source = False`** | **an empty value drops the page.** It is **the URL ubCode fetches the page's body from**, `{base}/{rst_source_path}` — the raw source Sphinx publishes under `_sources/` — so it must be a path the site actually serves; a value that is not a safe site-relative path (absolute, another scheme, `//host`, a `..` segment) is never handed out as a fetch handle. It is also **the catalog's key**: pages are sorted and deduplicated on it and looked up by bisection on it, so two pages with one value collapse into one. The docname is derived from it by stripping a leading `/`, a `_sources/` prefix, then a `.txt` suffix, then a `.rst` suffix |
| `html_path` | `builder.get_target_uri(docname)`, relative to the output root: `guide/install.html`; under `dirhtml` `guide/install/`, `x/` for a document named `x/index`, and `""` for the document named `index` (Sphinx keys this on the docname, not on `root_doc`) | joined onto the site's base URL — an already-absolute `http(s)` value is used verbatim instead; an empty value falls back to `rst_source_path`; a page whose resulting URL is not absolute `http(s)` is dropped. It is the page's citation URL |
| `title` | the document's title as text; for a document with no title, Sphinx's placeholder **`"<no title>"`** — Sphinx records a title node for every document it reads, so a built page is never written with `""` (that is only for a docname the environment holds no title for) | an empty value falls back to the docname — which therefore is not reached for an untitled Sphinx-built page: it arrives titled `<no title>` |
| `sections` | the titles of the direct subsections of the document's first top-level section, in document order; `[]` when there is none | used as-is |
| `summary` | the text of the first `.. page-summary::` directive in the document, stripped; `""` when there is none | used as-is |

The consumer also drops a page whose docname's last path segment is one of `genindex`,
`search`, `py-modindex`, `404` or `opensearch`.

## Limits on the consumer's side

- **4 MiB** (`AI_INDEX_MAX_BYTES`): a larger file is a failed fetch, and the source falls
  back to its `objects.inv` for pages (titles only).
- **10 000 pages** (`MAX_CATALOG_PAGES`): the first 10 000 kept pages, in the file's
  order, are used and the overflow is recorded as a degradation.
- A missing or unparseable file is a failed fetch too, with the same `objects.inv`
  fallback.

## Edges worth knowing

- **`html_copy_source = False`** makes every `rst_source_path` empty, so ubCode reads such a
  site's index as **zero pages** — and because the file itself was fetched and parsed, the
  `objects.inv` page fallback does not apply. A site that ubCode is to read must keep
  Sphinx's default `html_copy_source = True`.
- **`dirhtml`** writes `html_path = ""` for the document named `index`; the consumer then
  falls back to `rst_source_path`, so that page's citation URL is
  `<base>/_sources/index.rst.txt`. The sites ubCode reads build `html`.
- **A non-`.rst` source** (a MyST page, `_sources/x.md.txt`) keeps its `.md` in the
  consumer's docname (`x.md`); that only affects the empty-title fallback and the
  excluded-docname match.
- **Parallel builds** are supported: the per-document data lives on the build environment
  and is merged from the workers at `env-merge-info`, and purged at `env-purge-doc`.

## Changing the contract

The version string is the producer's only way to announce a change, and the consumer does
not read it today. So a new field is free; anything else — removing, renaming or changing
the meaning of a field, changing a field's type (a nullable `title`, say, rejects the
whole file), or changing when the file is written — needs a ubCode change first or
alongside, and a new `version` value. `rst_source_path` is the sharpest case: it is the
URL ubCode fetches every page body from, so a value the site does not serve under
`_sources/` (the repository path of the source, say) would leave every page listed and
every body fetch failing.

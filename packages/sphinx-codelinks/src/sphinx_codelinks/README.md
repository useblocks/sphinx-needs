# CodeLinks

## Overview

This is a Sphinx extension to extract Sphinx-Needs items from source files
such as C, C++ and others.

The need items are defined in the source files as comments and can be used to define
test case specifications or implementation markers.

Various definition styles are supported, such as one-line, multi-line or raw RST.

The project consists of the following three components:

- Source Discovery: determines list of source files from a given directory
- Virtual Docs: extract need annotations while keeping the source map
- Source Tracing: Sphinx extension to represent the collected the needs in the documentation

`Source Discovery` and `Virtual Docs` can be used as `APIs` or `CLI tools`.
The detail usages can be found in the [test cases](./tests).

The library is built to be

- ⚡ fast for large code bases and
- 📃 support a multitude of languages.

## Source Discovery

Recursively collect the file paths from a given directory.
It can be configured to respect `.gitignore`.

## Virtual Docs

Virtual Docs parses the discoverd files and

- extracts the need items from the comments in the source files.
- extracts additional metadata such as extra options and links.
- generates virtual documents containing the above-mentioned information into `json` files.
- caches virtual docs for incremental builds.
- keeps the source map to the path and line number of the original source files.

## CodeLinks

CodeLinks is a Sphinx Extension based on Sphinx-Needs. It provides the directive `src-tracing`
to collect the needs defined in source files by using `Source Discovery` and `Virtual Docs`
under the hood.

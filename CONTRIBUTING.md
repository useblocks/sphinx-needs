# Contributing

This repository is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
holding sphinx-needs and its sibling packages under `packages/`. The full guide, from
installing the development environment to running each package's tests and docs, is the
[Contributing page of the sphinx-needs documentation](https://sphinx-needs.readthedocs.io/en/latest/contributing.html);
`AGENTS.md` at the root describes the layout and the commands.

**Issues**: use the issue form and pick the package from its *Package* dropdown. Feature
ideas and questions go to the [discussions](https://github.com/useblocks/sphinx-needs/discussions).

**Pull requests are written by people.** A pull request that was generated automatically
from an issue, by an account that has not read the code, run the tests or taken part in the
discussion, typically within hours of the issue being filed, is closed without review,
whatever its content. We cannot tell a good one from a bad one without the full review a
change of our own would get, and its author knows nothing of the tools this repository
serves or of where the change sits in our plans. Using an AI assistant for your own
work is fine: you have read the change, you have tested it, and you answer for it. The pull
request template asks you to say so.

Every pull request needs a description of the change, tests for it, documentation where
behaviour changes, a changelog entry for the package, and a green `uv run poe lint` and
`uv run poe typecheck`. A maintainer approves the CI run of a pull request from outside the
organisation before it starts.

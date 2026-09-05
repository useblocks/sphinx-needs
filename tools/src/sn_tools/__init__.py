"""The workspace's own tooling: the manifest fences and the release plan.

No ``__version__`` here, deliberately: this member is never released, and
``check_workspace.py``'s check (5) skips virtual members by rule -- it would also not
find this package by derivation, since the distribution is `sphinx-needs-workspace-tools`
and the module is `sn_tools`.
"""

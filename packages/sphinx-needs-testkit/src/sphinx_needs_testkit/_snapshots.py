"""Syrupy snapshot support that more than one suite needs.

Only the doctree one lives here. sphinx-codelinks' anchors and extraction snapshots stay
in that package: they serialise its own data structures, and a snapshot extension whose
only consumer is one suite is not shared code, it is that suite's code in a shared place.
"""

from __future__ import annotations

from docutils.nodes import document
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


class DoctreeSnapshotExtension(SingleFileSnapshotExtension):
    """A doctree as ``pformat()`` text, with the two build-specific attributes removed.

    ``source`` is a temporary path, and ``translation_progress`` (sphinx 7.1) records how
    much of the document is translated; neither is a property of the doctree under test,
    and both change the snapshot from run to run.
    """

    _write_mode = WriteMode.TEXT
    file_extension = "doctree.xml"

    def serialize(self, data, **kwargs):
        if not isinstance(data, document):
            raise TypeError(f"Expected document, got {type(data)}")
        doc = data.deepcopy()
        doc["source"] = "<source>"  # this will be a temp path
        doc.attributes.pop("translation_progress", None)  # added in sphinx 7.1
        return doc.pformat()

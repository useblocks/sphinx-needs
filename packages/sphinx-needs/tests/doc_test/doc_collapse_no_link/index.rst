TEST DOCUMENT
=============

A need, so that the page carries a collapse control, and an ``a.no_link`` anchor, which
``sphinx_needs_collapse.js`` keeps from navigating.

Nothing in sphinx-needs' own layouts writes that class today: ``no_link=True`` on the
layout's ``image()`` function produces ``no-scaled-link`` on the image, not ``no_link`` on
an anchor. A project's own ``needs_layouts`` or raw markup can, though, which is what the
block below stands in for -- without it the branch has no page to run on.

.. req:: Test requirement
   :id: RQ_001

   Some content.

.. raw:: html

   <p><a class="no_link" href="#nowhere">an anchor that must not navigate</a></p>

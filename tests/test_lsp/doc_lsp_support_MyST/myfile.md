# My Markdown file example title

Some **text**!

```{eval-rst}
.. req:: MD REQ Title
   :id: REQ_2
   :status: open

   some stuff from md req.
```

```{spec} MD SPEC title
:id: SPEC_2
:status: open

MD Spec test content.
```

:need:`SPEC_2`

:need:`REQ_3`

:need:`REQ_1`

:need:`->`

:need:`->req>`

:need:`->req>myfile.md>`

:need:`->req>md_subfolder/`

:need:`->req>md_subfolder/MySecond.md>`

{need}`->`

{need}`->req>`

{need}`->req>myfile.md>`

{need}`->req>md_subfolder/`

{need}`->req>md_subfolder/MySecond.md>`

:need

.. req

Changelog & License
===================

License
-------

.. include:: ../LICENSE


0.7.3
-----
:Released: under development

0.7.2
-----
:Released: 08.10.2021

* Improvement: New config option :ref:`needs_builder_filter` to define a filter for the needs builder.
  (`#342 <https://github.com/useblocks/sphinxcontrib-needs/issues/342>`_)
* Improvement: Added option ``json_path`` for :ref:`needs_external_needs` to support external needs from local ``needs.json`` files.
  (`#339 <https://github.com/useblocks/sphinxcontrib-needs/issues/339>`_)
* Improvement: Providing :ref:`needs_table_classes` to allow to set custom table css classes, to better support
  themes like ReadTheDocs.
  (`#305 <https://github.com/useblocks/sphinxcontrib-needs/issues/305>`_)
* Improvement: Supporting user defined filter code function for :ref:`needs_warnings`
  (`#345 <https://github.com/useblocks/sphinxcontrib-needs/issues/345>`_)
* Improvement: Supporting caption for :ref:`needtable`
  (`#348 <https://github.com/useblocks/sphinxcontrib-needs/issues/348>`_)
* Improvement: New config option :ref:`needs_filter_data` to allow to use custom data inside a :ref:`filter_string`
  (`#317 <https://github.com/useblocks/sphinxcontrib-needs/issues/317>`_)
* Improvement: API to register warnings
  (`#343 <https://github.com/useblocks/sphinxcontrib-needs/issues/343>`_)
* Bugfix: Scrolling tables improved and ReadTheDocs Tables fixed
  (`#305 <https://github.com/useblocks/sphinxcontrib-needs/issues/305>`_)
* Bugfix: :ref:`needtable` need parts 'id' column is not linked
  (`#336 <https://github.com/useblocks/sphinxcontrib-needs/issues/336>`_)
* Bugfix: :ref:`needtable` need parts 'incoming' column is empty
  (`#336 <https://github.com/useblocks/sphinxcontrib-needs/issues/336>`_)
* Bugfix: :ref:`needs_warnings` not written to error log.
  (`#344 <https://github.com/useblocks/sphinxcontrib-needs/issues/344>`_)
* Improvement: Providing :ref:`needs_warnings_always_warn` to raise sphinx-warnings for each not passed :ref:`needs_warnings`.
  (`#344 <https://github.com/useblocks/sphinxcontrib-needs/issues/344>`_)
* Bugfix: :ref:`needimport` relative path not consistent to Sphinx default directives.
  (`#351 <https://github.com/useblocks/sphinxcontrib-needs/issues/351>`_)
* Bugfix: unstable build with :ref:`needs_external_needs`
  (`#341 <https://github.com/useblocks/sphinxcontrib-needs/issues/341>`_)

0.7.1
-----
:Released: 21.07.2021

* Improvement: Support for parallel sphinx-build when using ``-j`` option
  (`#319 <https://github.com/useblocks/sphinxcontrib-needs/issues/319>`_)
* Improvement: Better ``eval()`` handling for filter strings
  (`#328 <https://github.com/useblocks/sphinxcontrib-needs/issues/328>`_)
* Improvement: Internal :ref:`performance measurement <performance>` script
* Improvement: :ref:`Profiling support <profiling>` for selected functions

0.7.0
-----
:Released: 06.07.2021

* Improvement: Providing :ref:`needs_external_needs` to allow usage and referencing of external needs.
  (`#137 <https://github.com/useblocks/sphinxcontrib-needs/issues/137>`_)
* Improvement: New directive :ref:`needextend` to modify or extend existing needs.
  (`#282 <https://github.com/useblocks/sphinxcontrib-needs/issues/282>`_)
* Improvement: Allowing :ref:`needtable_custom_titles` for :ref:`needtable`.
  (`#299 <https://github.com/useblocks/sphinxcontrib-needs/issues/299>`_)
* Bugfix: :ref:`needextend` does not support usage of internal options.
  (`#318 <https://github.com/useblocks/sphinxcontrib-needs/issues/318>`_)
* Bugfix: :ref:`needtable` shows attributes with value ``False`` again.
* Bugfix: ``:hide:`` and ``:collapse: True`` are working inside :ref:`needimport`.
  (`#284 <https://github.com/useblocks/sphinxcontrib-needs/issues/284>`_,
  `#294 <https://github.com/useblocks/sphinxcontrib-needs/issues/294>`_)
* Bugfix: :ref:`needpie` amount labels get calculated correctly.
  (`#297 <https://github.com/useblocks/sphinxcontrib-needs/issues/297>`_)

0.6.3
-----
:Released: 18.06.2021

* Improvement: Dead links (references to not found needs) are supported and configurable by :ref:`allow_dead_links`.
  (`#116 <https://github.com/useblocks/sphinxcontrib-needs/issues/116>`_)
* Improvement: Introducing :ref:`need_func` to execute :ref:`dynamic_functions` inline.
  (`#133 <https://github.com/useblocks/sphinxcontrib-needs/issues/133>`_)
* Improvement: Support for :ref:`multiline_option` in templates.
* Bugfix: needflow: links  for need-parts get correctly calculated.
  (`#205 <https://github.com/useblocks/sphinxcontrib-needs/issues/205>`_)
* Bugfix: CSS update for ReadTheDocsTheme to show tables correctly.
  (`#263 <https://github.com/useblocks/sphinxcontrib-needs/issues/263>`_)
* Bugfix: CSS fix for needtable :ref:`needtable_style_row`.
  (`#195 <https://github.com/useblocks/sphinxcontrib-needs/issues/195>`_)
* Bugfix: ``current_need`` var is accessible in all need-filters.
  (`#169 <https://github.com/useblocks/sphinxcontrib-needs/issues/169>`_)
* Bugfix: Sets defaults for color and style of need type configuration, if not set by user.
  (`#151 <https://github.com/useblocks/sphinxcontrib-needs/issues/151>`_)
* Bugfix: :ref:`needtable` shows horizontal scrollbar for tables using datatables style.
  (`#271 <https://github.com/useblocks/sphinxcontrib-needs/issues/271>`_)
* Bugfix: Using ``id_complete`` instead of ``id`` in filter code handling.
  (`#156 <https://github.com/useblocks/sphinxcontrib-needs/issues/156>`_)
* Bugfix: Dynamic Functions registration working for external extensions.
  (`#288 <https://github.com/useblocks/sphinxcontrib-needs/issues/288>`_)

0.6.2
-----
:Released: 30.04.2021

* Improvement: Parent needs of nested needs get collected and are available in filters.
  (`#249 <https://github.com/useblocks/sphinxcontrib-needs/issues/249>`_)
* Bugfix: Copying static files during sphinx build is working again.
  (`#252 <https://github.com/useblocks/sphinxcontrib-needs/issues/252>`_)
* Bugfix: Link function for layouts setting correct text.
  (`#251 <https://github.com/useblocks/sphinxcontrib-needs/issues/251>`_)


0.6.1
-----
:Released: 23.04.2021

* Support: Removes support for Sphinx version <3.0 (Sphinx 2.x may still work, but it gets not tested).
* Improvement: Internal change to poetry, nox and github actions.
  (`#216 <https://github.com/useblocks/sphinxcontrib-needs/issues/216>`_)
* Bugfix: Need-service calls get mocked during tests, so that tests don't need reachable external services anymore.
* Bugfix: No warning is thrown anymore, if :ref:`needservice` can't find a service config in ``conf.py``
  (`#168 <https://github.com/useblocks/sphinxcontrib-needs/issues/168>`_)
* Bugfix: Needs nodes get ``ids`` set directly, to avoid empty ids given by sphinx or other extensions for need-nodes.
  (`#193 <https://github.com/useblocks/sphinxcontrib-needs/issues/193>`_)
* Bugfix: :ref:`needimport` supports extra options and extra fields.
  (`#227 <https://github.com/useblocks/sphinxcontrib-needs/issues/227>`_)
* Bugfix: Checking for ending `/` of given github api url.
  (`#187 <https://github.com/useblocks/sphinxcontrib-needs/issues/187>`_)
* Bugfix: Using correct indention for pre and post_template function of needs.
* Bugfix: Certain log message don't use python internal `id` anymore.
  (`#257 <https://github.com/useblocks/sphinxcontrib-needs/issues/225>`_)
* Bugfix: JS-code for meta area collapse is working again.
  (`#242 <https://github.com/useblocks/sphinxcontrib-needs/issues/242>`_)


0.6.0
-----

* Improvement: Directive :ref:`needservice` added, which allow to include data from external services like Jira or github.
  See also :ref:`services`
  (`#163 <https://github.com/useblocks/sphinxcontrib-needs/issues/163>`_)
* Improvement: :ref:`github_service` added to fetch issues, pr or commits from GitHub or GitHub Enterprise.
* Bugfix: Role :ref:`role_need_outgoing` shows correct link instead of *None*
  (`#160 <https://github.com/useblocks/sphinxcontrib-needs/issues/160>`_)


0.5.6
-----

* Bugfix: Dynamic function registration via API supports new internal function handling
  (`#147 <https://github.com/useblocks/sphinxcontrib-needs/issues/147>`_)
* Bugfix: Deactivated linked gantt elements in :ref:`needgantt`, as PlantUML does not support them in its
  latest version (not beta).

0.5.5
-----
* Improvement: Added :ref:`needsequence` directive. (`#144 <https://github.com/useblocks/sphinxcontrib-needs/issues/144>`_)
* Improvement: Added :ref:`needgantt` directive. (`#146 <https://github.com/useblocks/sphinxcontrib-needs/issues/146>`_)
* Improvement: Added two new need-options: :ref:`need_duration` and :ref:`need_completion`
* Improvement: Configuration option :ref:`needs_duration_option` and :ref:`needs_completion_option` added
* Bugfix: Using of `tags.has() <https://www.sphinx-doc.org/en/master/usage/configuration.html#conf-tags>`_ in
  ``conf.py`` does not raise an exception anymore. (`#142 <https://github.com/useblocks/sphinxcontrib-needs/issues/142>`_)
* Improvement: Clean up of internal configuration handling and avoiding needs_functions to get pickled by sphinx.


0.5.4
-----
* Improvement: Added options :ref:`need_pre_template` and :ref:`need_post_template` for needs. (`#139 <https://github.com/useblocks/sphinxcontrib-needs/issues/139>`_)
* Bugfix: Setting correct default value for :ref:`needs_statuses` (`#136 <https://github.com/useblocks/sphinxcontrib-needs/issues/136>`_)
* Bugfix: Dynamic functions can be used in links (text and url) now.

0.5.3
-----
* Improvement: Added ``transparent`` for transparent background to needflow configurations.
* Improvement: :ref:`needflow` uses directive argument as caption now.
* Improvement: Added option :ref:`needflow_align` to align needflow images.
* Improvement: Added option :ref:`needflow_scale` to scale needflow images. (`#127 <https://github.com/useblocks/sphinxcontrib-needs/issues/127>`_)
* Improvement: Added option :ref:`needflow_highlight` to :ref:`needflow`. (`#128 <https://github.com/useblocks/sphinxcontrib-needs/issues/128>`_)
* Improvement: :ref:`need_count` supports :ref:`ratio calculation <need_count_ratio>`. (`#131 <https://github.com/useblocks/sphinxcontrib-needs/issues/131>`_)
* Improvement: :ref:`needlist`, :ref:`needtable` and :ref:`needflow` support :ref:`filter_code`. (`#132 <https://github.com/useblocks/sphinxcontrib-needs/issues/132>`_)
* Improvement: :ref:`needflow` caption is a link to the original image file. (`#129 <https://github.com/useblocks/sphinxcontrib-needs/issues/129>`_)
* Bugfix: :ref:`need_template` can now be set via :ref:`needs_global_options`.
* Bugfix: Setting correct urls for needs in :ref:`needflow` charts.
* Bugfix: Setting correct image candidates (`#134 <https://github.com/useblocks/sphinxcontrib-needs/issues/134>`_)

0.5.2
-----
* Improvement: ``Sphinx-Needs`` configuration gets checked before build. (`#118 <https://github.com/useblocks/sphinxcontrib-needs/issues/118>`_)
* Improvement: ``meta_links_all`` :ref:`layout function <layout_functions>` now supports an exclude parameter
* Improvement: :ref:`needflow`'s :ref:`connection line and arrow type <needflow_style_start>` can be configured.
* Improvement: Configurations added for :ref:`needflow`. Use :ref:`needs_flow_configs` to define them and :ref:`needflow_config` for activation.
* Improvement: :ref:`needflow` option :ref:`needflow_debug` added, which prints the generated PlantUML code after the flowchart.
* Improvement: Supporting Need-Templates by providing need option :ref:`need_template` and
  configuration option :ref:`needs_template_folder`. (`#119 <https://github.com/useblocks/sphinxcontrib-needs/issues/119>`_)
* Bugfix: :ref:`needs_global_options` handles None values correctly. ``style`` can now be set.
* Bugfix: :ref:`needs_title_from_content` takes ``\n`` and ``.`` as delimiter.
* Bugfix: Setting css-attribute ``white-space: normal`` for all need-tables, which is set badly in some sphinx-themes.
  (Yes, I'm looking at you *ReadTheDocs theme*...)
* Bugfix: ``meta_all`` :ref:`layout function <layout_functions>` also outputs extra links and the `no_links`
  parameter now works as expected
* Bugfix: Added need-type as css-class back on need. Css class name is ``needs_type_(need_type attribute)``.
  (`#124 <https://github.com/useblocks/sphinxcontrib-needs/issues/124>`_)
* Bugfix: Need access inside list comprehensions in :ref:`filter_string` is now working.

0.5.1
-----
* Improvement: Added :ref:`needextract` directive to mirror existing needs for special outputs. (`#66 <https://github.com/useblocks/sphinxcontrib-needs/issues/66>`_)
* Improvement: Added new styles ``discreet`` and ``discreet_border``.
* Bugfix: Some minor css fixes for new layout system.

0.5.0
-----

* Improvement: Introduction of needs :ref:`layouts_styles`.
* Improvement: Added config options :ref:`needs_layouts` and :ref:`needs_default_layout`.
* Improvement: Added :ref:`needpie` which draws pie-charts based on :ref:`filter_string`.
* Improvement: Added config option :ref:`needs_warnings`. (`#110 <https://github.com/useblocks/sphinxcontrib-needs/issues/110>`_)
* Bugfix: Need css style name is now based on need-type and not on the longer, whitespace-containing type name.
  Example: ``need-test`` instead of not valid ``need-test case``. (`#108 <https://github.com/useblocks/sphinxcontrib-needs/issues/108>`_)
* Bugfix: No more exception raise if ``copy`` value not set inside :ref:`needs_extra_links`.
* Improvement: Better log message, if required id is missing. (`#112 <https://github.com/useblocks/sphinxcontrib-needs/issues/112>`_)

* Removed: Configuration option :ref:`needs_collapse_details`. This is now realized by :ref:`layouts`.
* Removed: Configuration option :ref:`needs_hide_options`. This is now realized by :ref:`layouts`.
* Removed: Need option :ref:`need_hide_status`. This is now realized by :ref:`layouts`.
* Removed: Need option :ref:`need_hide_tags`. This is now realized by :ref:`layouts`.

**WARNING**: This version changes a lot the html output and therefore the needed css selectors. So if you are using
custom css definitions you need to update them.

0.4.3
-----

* Improvement: Role :ref:`role_need` supports standard sphinx-ref syntax. Example: ``:need:`custom name <need_id>```
* Improvement: Added :ref:`global_option_filters` to set values of global options only under custom circumstances.
* Improvement: Added sorting to :ref:`needtable`. See :ref:`needtable_sort` for details.
* Improvement: Added dynamic function :ref:`links_content` to calculated links to other needs automatically from need-content.
  (`#98 <https://github.com/useblocks/sphinxcontrib-needs/issues/98>`_)
* Improvement: Dynamic function :ref:`copy` supports uppercase and lowercase transformation.
* Improvement: Dynamic function :ref:`copy` supports filter_string.
* Bugfix: Fixed corrupted :ref:`dynamic_functions` handling for ``tags`` and other list options.
  (`#100 <https://github.com/useblocks/sphinxcontrib-needs/issues/100>`_)
* Bugfix: Double entries for same need in :ref:`needtable` fixed. (`#93 <https://github.com/useblocks/sphinxcontrib-needs/issues/93>`_)

0.4.2
-----

* Improvement: Added ``signature`` information to need-object. Usable inside :ref:`filter_string`.
  Mainly needed by `Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`_ to link imported
  test cases to needs documented by
  `sphinx-autodoc <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_.

0.4.1
-----
* Improvement: Added :ref:`need_style` option to allow custom styles for needs.
* Improvement: Added :ref:`needtable_style_row` option to allow custom styles for table rows and columns.


0.4.0
-----
* Improvement: Provides API for other sphinx-extensions. See :ref:`api` for documentation.
* Improvement: Added :ref:`support` page.
* Bugfix: Fixed deprecation warnings to support upcoming Sphinx3.0 API.

0.3.15
------
* Improvement: In filter operations, all needs can be accessed  by using keyword ``needs``.
* Bugfix: Removed prefix from normal needs for needtable (`#97 <https://github.com/useblocks/sphinxcontrib-needs/issues/97>`_)

0.3.14
------
* Improvement: Added config option :ref:`needs_role_need_max_title_length` to define the maximum title length of
  referenced needs. (`#95 <https://github.com/useblocks/sphinxcontrib-needs/issues/95>`_)

0.3.13
------
* Bugfix: Filters on needs with ``id_parent`` or ``id_complete`` do not raise an exception anymore and filters
  gets executed correctly.

0.3.12
------
* Improvement: Tables can be sorted by any alphanumeric option. (`#92 <https://github.com/useblocks/sphinxcontrib-needs/issues/92>`_)
* Improvement: :ref:`need_part` are now embedded in their parent need, if :ref:`needflow` is used. (`#83 <https://github.com/useblocks/sphinxcontrib-needs/issues/83>`_)
* Bugfix: Links to :ref:`need_part` are no longer rendered to parent need, instead the link goes directly to the need_part. (`#91 <https://github.com/useblocks/sphinxcontrib-needs/issues/91>`_)
* Bugfix: Links in :ref:`needflow` get shown again by default (`#90 <https://github.com/useblocks/sphinxcontrib-needs/issues/90>`_)


0.3.11
------
* Improvement: Added config option :ref:`needs_extra_links` to define additional link types like *blocks*, *tested by* and more.
  Supports also style configuration and custom presentation names for links.
* Improvement: Added :ref:`export_id` option for filter directives to export results of filters to ``needs.json``.
* Improvement: Added config option :ref:`needs_flow_show_links` and related needflow option :ref:`needflow_show_link_names`.
* Improvement: Added config option :ref:`needs_flow_link_types` and related needflow option :ref:`needflow_link_types`.
* Bugfix: Unicode handling for Python 2.7 fixed. (`#86 <https://github.com/useblocks/sphinxcontrib-needs/issues/86>`_)

0.3.10
------
* Bugfix: **type** was missing in output of builder :ref:`needs_builder` (`#79 <https://github.com/useblocks/sphinxcontrib-needs/issues/79>`_)
* Bugfix: **needs_functions** parameter in *conf.py* created a sphinx error, if
  containing python methods. Internal workaround added, so that usage of own
  :ref:`dynamic_functions` stays the same as in prior versions (`#78 <https://github.com/useblocks/sphinxcontrib-needs/issues/78>`_)


0.3.9
-----
* Bugfix: Grubby tag/link strings in needs, which define empty links/tags, produce a warning now.
* Bugfix: Better logging of document location, if a filter string is not valid.
* Bugfix: Replaced all print-statements with sphinx warnings.

0.3.8
-----

* Improvement: :ref:`need_part` has now attributes `id_parent` and `id_complete`, which can be referenced
  in :ref:`filter_string`.
* Improvement: :ref:`needtable` supports presentation of filtered :ref:`need_part` (without showing parent need).

0.3.7
-----
* Improvement: :ref:`filter_string` now supports the filtering of :ref:`need_part`.
* Improvement: The ID of a need is now printed as link, which can easily be used for sharing. (`#75 <https://github.com/useblocks/sphinxcontrib-needs/issues/75>`_)
* Bugfix: Filter functionality in different directives are now using the same internal filter function.
* Bugfix: Reused IDs for a :ref:`need_part` are now detected and a warning gets printed. (`#74 <https://github.com/useblocks/sphinxcontrib-needs/issues/74>`_)

0.3.6
-----
* Improvement: Added needtable option :ref:`needtable_show_parts`.
* Improvement: Added configuration option :ref:`needs_part_prefix`.
* Improvement: Added docname to output file of builder :ref:`needs_builder`
* Bugfix: Added missing needs_import template to MANIFEST.ini.

0.3.5
-----
* Bugfix: A :ref:`need_part` without a given ID gets a random id based on its content now.
* Bugfix: Calculation of outgoing links does not crash, if need_parts are involved.


0.3.4
-----
* Bugfix: Need representation in PDFs were broken (e.g. all meta data on one line).


0.3.3
-----
* Bugfix: Latex and Latexpdf are working again.

0.3.2
-----
* Bugfix: Links to parts of needs (:ref:`need_part`) are now stored and presented as *links incoming* of target link.

0.3.1
-----
* Improvement: Added dynamic function :ref:`check_linked_values`.
* Improvement: Added dynamic function :ref:`calc_sum`.
* Improvement: Added role :ref:`need_count`, which shows the amount of found needs for a given filter-string.
* Bugfix: Links to :ref:`need_part` in :ref:`needflow` are now shown correctly as extra line between
   need_parts containing needs.
* Bugfix: Links to :ref:`need_part` in :ref:`needtable` are now shown and linked correctly in tables.

0.3.0
-----
* Improvement: :ref:`dynamic_functions` are now available to support calculation of need values.
* Improvement: :ref:`needs_functions` can be used to register and use own dynamic functions.
* Improvement: Added :ref:`needs_global_options` to set need values globally for all needs.
* Improvement: Added :ref:`needs_hide_options` to hide specific options of all needs.
* Bugfix: Removed needs are now deleted from existing needs.json (`#68 <https://github.com/useblocks/sphinxcontrib-needs/issues/68>`_)
* Removed: :ref:`needs_template` and :ref:`needs_template_collapse` are no longer supported.

0.2.5
-----
* Bugfix: Fix for changes made in 0.2.5.

0.2.4
-----
* Bugfix: Fixed performance issue (`#63 <https://github.com/useblocks/sphinxcontrib-needs/issues/63>`_)

0.2.3
-----
* Improvement: Titles can now be made optional.  See :ref:`needs_title_optional`. (`#49 <https://github.com/useblocks/sphinxcontrib-needs/issues/49>`_)
* Improvement: Titles be auto-generated from the first sentence of a requirement.  See :ref:`needs_title_from_content` and :ref:`title_from_content`. (`#49 <https://github.com/useblocks/sphinxcontrib-needs/issues/49>`_)
* Improvement: Titles can have a maximum length.  See :ref:`needs_max_title_length`. (`#49 <https://github.com/useblocks/sphinxcontrib-needs/issues/49>`_)

0.2.2
-----
* Improvement: The sections, to which a need belongs, are now stored, filterable and exported in ``needs.json``. See updated :ref:`option_filter`. (`#53 <https://github.com/useblocks/sphinxcontrib-needs/pull/53>`_ )
* Improvement: Project specific options for needs are supported now. See :ref:`needs_extra_options`. (`#48 <https://github.com/useblocks/sphinxcontrib-needs/pull/48>`_ )
* Bugfix: Logging fixed (`#50 <https://github.com/useblocks/sphinxcontrib-needs/issues/50>`_ )
* Bugfix: Tests for custom styles are now working when executed with all other tests (`#47 <https://github.com/useblocks/sphinxcontrib-needs/pull/47>`_)


0.2.1
-----
* Bugfix: Sphinx warnings fixed, if need-collapse was used. (`#46 <https://github.com/useblocks/sphinxcontrib-needs/issues/46>`_)
* Bugfix: dark.css, blank.css and common.css used wrong need-container selector. Fixed.

0.2.0
-----
* Deprecated: :ref:`needfilter` is replaced by :ref:`needlist`, :ref:`needtable` or :ref:`needflow`. Which support additional options for related layout.
* Improvement: Added :ref:`needtable` directive.
* Improvement: Added `DataTables <https://datatables.net/>`_ support for :ref:`needtable` (including table search, excel/pdf export and dynamic column selection).
* Improvement: Added :ref:`needs_id_regex`, which takes a regular expression and which is used to validate given IDs of needs.
* Improvement: Added meta information shields on documentation page
* Improvement: Added more examples to documentation
* Bugfix: Care about unneeded separator characters in tags (`#36 <https://github.com/useblocks/sphinxcontrib-needs/issues/36>`_)
* Bugfix: Avoiding multiple registration of resource files (js, css), if sphinx gets called several times (e.g. during tests)
* Bugfix: Needs with no status shows up on filters (`#45 <https://github.com/useblocks/sphinxcontrib-needs/issues/45>`_)
* Bugfix: Supporting Sphinx 1.7 (`#41 <https://github.com/useblocks/sphinxcontrib-needs/issues/41>`_)

0.1.49
------
* Bugfix: Supporting plantnuml >= 0.9 (`#38 <https://github.com/useblocks/sphinxcontrib-needs/issues/38>`_)
* Bugfix: need_outgoing does not crash, if given need-id does not exist (`#32 <https://github.com/useblocks/sphinxcontrib-needs/issues/32>`_)

0.1.48
------
* Improvement: Added configuration option :ref:`needs_role_need_template`.
* Bugfix: Referencing not existing needs will result in build warnings instead of a build crash.
* Refactoring: needs development files are stored internally under *sphinxcontrib/needs*, which is in sync with
   most other sphinxcontrib-packages.

0.1.47
------
* Bugfix: dark.css was missing in MANIFEST.in.
* Improvement: Better output, if configured needs_css file can not be found during build.

0.1.46
------
* Bugfix: Added python2/3 compatibility for needs_import.

0.1.45
------
* Bugfix: needs with no status are handled the correct way now.

0.1.44
------
* Bugfix: Import statements are checked, if Python 2 or 3 is used.

0.1.43
------
* Improvement: Added "dark.css" as style
* Bugfix: Removed "," as as separator of links in need presentation.

0.1.42
------
* Improvement: Added config parameter :ref:`needs_css`, which allows to set a css file.
* Improvement: Most need-elements (title, id, tags, status, ...) got their own html class attribute to support custom styles.
* Improvement: Set default style "modern.css" for all projects without configured :ref:`needs_css` parameter.

0.1.41
------

* Improvement: Added config parameters :ref:`needs_statuses` and :ref:`needs_tags` to allow only configured statuses/tags inside documentation.
* Bugfix: Added LICENSE file (MIT)

0.1.40
------
* Bugfix: Removed jinja activation

0.1.39
------
* Bugfix: Added missing needimport_template.rst to package
* Bugfix: Corrected version param of needimport

0.1.38
------
* Improvement: **:links:**, **:tags:** and other list-based options can handle "," as delimiter
   (beside documented ";"). No spooky errors are thrown anymore if "," is used accidentally.

0.1.37
------
* Bugfix: Implemented 0.1.36 bugfix also for :ref:`needfilter` and :ref:`needimport`.

0.1.36
------
* Bugfix: Empty **:links:** and **:tags:** options for :ref:`need` raise no error during build.

0.1.35
------
* Improvement/Bug: Updated default node_template to use less space for node parameter representation
* Improvement: Added **:filter:** option to :ref:`needimport` directive
* Bugfix: Set correct default value for **need_list** option. So no more warnings should be thrown during build.
* Bugfix: Imported needs gets sorted by id before adding them to the related document.

0.1.34
------
* Improvement: New option **tags** for :ref:`needimport` directive
* Bugfix: Handling of relative paths in needs builder

0.1.33
------
* New feature: Directive :ref:`needimport` implemented
* Improvement: needs-builder stores needs.json for all cases in the build directory (like _build/needs/needs.json) (See `issue comment <https://github.com/useblocks/sphinxcontrib-needs/issues/9#issuecomment-325010790>`_)
* Bugfix: Wrong version in needs.json, if an existing needs.json got imported
* Bugfix: Wrong need amount in initial needs.json fixed

0.1.32
------
* Bugfix: Setting correct working directory during conf.py import
* Bugfix: Better config handling, if Sphinx builds gets called multiple times during one single python process. (Configs from prio sphinx builds may still be active.)
* Bugifx: Some cleanups for using Sphinx >= 1.6

0.1.31
------

* Bugfix: Added missing dependency to setup.py: Sphinx>=1.6

0.1.30
------
* Improvement: Builder :ref:`needs_builder` added, which exports all needs to a json file.

0.1.29
------

* Bugfix: Build has crashed, if sphinxcontrib-needs was loaded but not a single need was defined.

0.1.28
------

* Bugfix: Added support for multiple sphinx projects initialisations/builds during a single python process call.
           (Reliable sphinxcontrib-needs configuration separation)

0.1.27
------

* New config: :ref:`needs_show_link_type`
* New config: :ref:`needs_show_link_title`

0.1.26
------

* Bugfix: Working placement of "," for links list produced by roles :ref:`role_need_outgoing`
   and :ref:`role_need_incoming`.

0.1.25
------

* Restructured code
* Restructured documentation
* Improvement: Role :ref:`role_need_outgoing` was added to print outgoing links from a given need
* Improvement: Role :ref:`role_need_incoming` was added to print incoming links to a given need

0.1.24
------

* Bugfix: Reactivated jinja execution for documentation.

0.1.23
------

* Improvement: :ref:`complex filter <filter>` for needfilter directive supports :ref:`regex searches <re_search>`.
* Improvement: :ref:`complex filter <filter>` has access to nearly all need variables (id, title, content, ...)`.
* Bugfix: If a duplicated ID is detected an error gets thrown.

0.1.22
------

* Improvement: needfilter directives supports complex filter-logic by using parameter :ref:`filter`.

0.1.21
------

* Improvement: Added word highlighting of need titles in linked pages of svg diagram boxes.

0.1.20
------

* Bugfix for custom needs_types: Parameter in conf.py was not taken into account.

0.1.19
------

* Added configuration parameter :ref:`needs_id_required`.
* Backwards compatibility changes:

* Reimplemented **needlist** as alias for :ref:`needfilter`
* Added *need* directive/need as part of the default :ref:`needs_types` configuration.

0.1.18
------

**Initial start for the changelog**

* Free definable need types (Requirements, Bugs, Tests, Employees, ...)
* Allowing configuration of needs with a

* directive name
* meaningful title
* prefix for generated IDs
* color

* Added **needfilter** directive
* Added layouts for needfilter:

* list (default)
* table
* diagram (based on plantuml)

* Integrated interaction with the activated plantuml sphinx extension

* Added role **need** to create a reference to a need by giving the id

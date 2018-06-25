Changelog
=========

0.2.2
-----
 * Improvement: Project specific options for needs are supported now. See :ref:`needs_extra_options`. (`#48 <https://github.com/useblocks/sphinxcontrib-needs/pull/48>`_ )
 * Bugfix: Logging fixed (`#50 <https://github.com/useblocks/sphinxcontrib-needs/issues/50>`_ )
 * Bugfix: Tests for custom styles are now working when executed with all other tests (`#47 <https://github.com/useblocks/sphinxcontrib-needs/pull/47>`_ )


0.2.1
-----
 * Bugfix: Sphinx warnings fixed, if need-collapse was used. (`#46 <https://github.com/useblocks/sphinxcontrib-needs/issues/46>`_ )
 * Bugfix: dark.css, blank.css and common.css used wrong need-container selector. Fixed.

0.2.0
-----
 * Deprecated: :ref:`needfilter` is replaced by needlist, :ref:`needtable` or needdiagram. Which support additional options for related layout.
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
 * Bugfix: need_outgoing does not crash, if given need-id does not exist (`#32 <https://github.com/useblocks/sphinxcontrib-needs/issues/32>`_ )

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
 * Added *need* directive/need as part of the default :ref:`need_types` configuration.

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

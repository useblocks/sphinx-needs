Changelog
=========

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

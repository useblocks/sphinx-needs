Changelog
=========

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

.. _github_service:

GitHub services
===============

As GitHub provides different kinds of information (e.g. issues, prs or commits), there is a specialised service
for each information type:

+ ``github-issues``
+ ``github-prs``
+ ``github-commits``

A service is available only when it is configured:
name it in :ref:`needs_services`, in **conf.py** or as a ``[needs.services.<name>]`` table of the :ref:`needs_from_toml` file.
An empty configuration will do:

.. code-block:: python

    needs_services = {"github-issues": {}}

.. code-block:: toml

    [needs.services.github-issues]

A configured service brings the fields its needs carry (``url``, ``user``, ``avatar``, ``service``, ``created_at``,
``updated_at``, ``closed_at``, and the options ``query``, ``specific``, ``max_amount``, ``max_content_lines`` and
``id_prefix``), its :ref:`need type <service_github_need_type>` and the :ref:`github layout <service_github_layout>`.
A project that configures none of the three has none of them.
A :ref:`needservice` naming a service that is not configured creates nothing,
and warns (``needs.load_service_need``) with the configuration to add.

They all have common configuration options and are using the same way of querying their data.
Therefore the below configuration is valid for all three services.

Each services creates normally multiple need objects for each element found by querying the GitHub API.

**Example of an imported github issue**:

.. code-block:: rst

    .. needservice:: github-issues
       :query: repo:useblocks/sphinx-needs node latexpdf
       :max_amount: 1
       :max_content_lines: 4

.. figure:: /_images/github_issue_1.png
   :scale: 80%

   Example of a github Issue collected with Sphinx-Needs.

Directive options, which can also used for normal needs, can also be set for ``needservice`` directive.
Also the content part of ``needservice`` is added as extra data to the end of the finally created needs.

**Example**:

.. code-block:: rst

    .. needservice:: github-issues
       :query: repo:useblocks/sphinx-needs node latexpdf
       :id_prefix: GH_
       :max_amount: 1
       :max_content_lines: 4
       :type: spec
       :author: Me
       :tags: github, awesome, issue, open
       :layout: clean
       :style: discreet

       Extra content for each new need

.. figure:: /_images/github_issue_2.png
   :scale: 80%

   Example of a github Issue collected with Sphinx-Needs.

Querying objects
----------------
There are two options for querying objects for GitHub:

:``query``: Performs a Github search
:``specific``: Gets a single, specific element from GitHub

Setting ``query`` or ``specific`` option is mandatory for services ``github-issues`` and ``github-prs``!

.. warning::

   GitHub counts the performed API requests and may reject new requests, if the rate limit is exceeded.
   This seems to be **10 requests per minute for search-API** for unauthenticated users.

   You can higher this limit to **30 requests**, if you provide a username and token in the service config.

   **Sphinx-Needs** will support you with the current rate limit status, if a request got rejected.

query
+++++
The imported objects are based on a query-string, which must be valid to the
`Github search syntax for issues and pull requests <https://docs.github.com/en/free-pro-team@latest/github/searching-for-information-on-github/searching-issues-and-pull-requests>`_.

To query for issues only, ``github-issues`` adds ``is:issue`` to the query string automatically.
Related to this, ``github-prs`` adds ``is:pr``.

**Example**:

This loads all open issues, which have the strings *needtable* and *viewports* in their data.

.. code-block:: rst

    .. needservice:: github-issues
       :query: repo:useblocks/sphinx-needs state:open needtable viewports


specific
++++++++
If only a single, specific object shall be documented, using ``query`` will not work, as the GitHub Search API
does not support query-options for getting a specific element.
Instead use ``specific`` and provide the unique reference in the syntax ``owner/repo/number``, for example
``useblocks/sphinx-needs/155``


**Example**:

This query fetches a specific pull request with the id 161.

.. code-block:: rst

    .. needservice:: github-prs
       :specific: useblocks/sphinx-needs/161

.. figure:: /_images/github_issue_3.png
   :scale: 80%

   Example of a github Issue collected with Sphinx-Needs.

.. _service_github_config:

Common Configuration
--------------------
All GitHub related services have a common set of configuration options,
set in :ref:`needs_services`: in the project's **conf.py** file,
or in a ``[needs.services.<name>]`` table of the :ref:`needs_from_toml` file.

:ref:`needs_services` must contain a key with the service name, e.g. ``github-issues``:
that key is what makes the service available, with no options too (``{}``).

The following key-value configuration parameters are known by all GitHub services:

:url: GitHub service instance url. Default: ``https://api.github.com/``
:username: Username if access to private repositories is needed.
:token: Personal GitHub token for login. Can be created in your `User profile page <https://github.com/settings/tokens>`_.
:download_avatars: ``True/False``, if avatars shall be downloaded. If ``False`` a default avatar is used.
                   Needed mostly for ``GitHub Enterprise``, as authentication for avatars may make some trouble.
:download_folder: Folder path for avatar downloads. Default: ``github_images``.
:need_type: Default need type to use, if no type got specified in directive options
:max_amount: The maximum amount of issues to report
:max_content_lines: Maximum amount of lines from issue/pr/commit content to be reported in need content.
:id_prefix: Prefix string for the final need id.
:layout: Layout to use for need. Default is ``github``. See :ref:`layouts` for details.

All options can be overwritten by setting them directly in the need service directive:

.. code-block:: rst

    .. needservice:: github-issues
       :query: repo:useblocks/sphinx-needs
       :type: test
       :max_amount: 10
       :max_content_lines: 2
       :id_prefix: GITHUB_UB_

**Example configuration for conf.py**:

.. code-block:: python

    needs_services = {
        'github-issues': {
            'url': 'https://api.github.com/',
            'need_type': 'spec',
            'max_amount': 2,
            'max_content_lines': 20,
            'id_prefix': 'GH_ISSUE_'
        }
    }

.. _service_github_layout:

Layout
++++++

The GitHub services are providing a new layout, called ``github``, which is used by default and is based on the
standard ``complete`` layout.
It is available when at least one of the three services is configured.
Sphinx-Needs registers it beside the configured layouts, not in the :ref:`needs_layouts` value:
a ``github`` entry of your own in :ref:`needs_layouts`,
or one an extension adds with :func:`~sphinx_needs.api.configuration.add_need_layout`, replaces it.

You can overwrite its usage by setting ``layout`` in the service configuration or by setting it directly in the
directive :ref:`needservice`.

.. code-block:: rst

    .. needservice:: github-issues
       :query: repo:useblocks/sphinx-needs node latexpdf
       :max_content_lines: 4
       :layout: focus_l
       :style: blue_border

.. figure:: /_images/github_issue_4.png
   :scale: 80%

   Example of a github Issue collected with Sphinx-Needs.

.. _service_github_need_type:

Need type
+++++++++
Each GitHub service creates a need type of its own, when it is configured:
``github-issues`` creates ``issue``, ``github-prs`` creates ``pr`` and ``github-commits`` creates ``commit``.
A service that is not configured creates no type, so a project configuring ``github-issues`` alone has ``issue``,
but no ``pr`` and no ``commit``.
These types are used by default by the related service, but its usage can be overwritten in the service configuration
by setting ``need_type`` or in the directive directly by setting ``type``.

The configuration (names, colors, diagram representation) can also be overwritten by configuring your own need
type in the configuration. Simply use :ref:`needs_types` for this.
A type of the same directive added by another extension with :func:`~sphinx_needs.api.configuration.add_need_type`,
whenever it is added, replaces it too.
Sphinx-Needs registers the type of each configured service beside the configured ones, not in the
:ref:`needs_types` value, after every configured or added type, and each gives way on its own:
configuring your own ``issue`` leaves ``pr`` and ``commit`` as they are.
An extension reading the need types sees them from a ``config-inited`` handler at a priority above 12.

.. _service_github_custom:

Custom service
--------------
The built-in services ``github-issues``, ``github-prs`` and ``github-commits`` support the cloud instance of
GitHub by default.

If a company internal ``GitHub Enterprise`` instance shall be addressed, you should configure an additional service to
deal with both (cloud and company instance) and being able to set company specific configuration options.

Please see the this example for a ``Github Enterprise`` configuration in your **conf.py** file:

.. code-block:: python

    from sphinx_needs.services.github import GithubService

    needs_services = {
        # Cloud GitHub configuration
        'github-issues': {
            'max_content_lines': 20,
            'id_prefix': 'GH_ISSUE_',
        },
        # GitHub Enterprise configuration
        'my-company-issues': {
            'class': GithubService,
            'class_init': {
                'gh_type': 'issue'
            },
            'url': 'https://github.my-company.com/api/v3/',
            'username': 'my_username',
            'token':  'my_github_token',
            'download_avatars': True,
            'download_folder': 'company-avatars',
            'max_content_lines': 20,
            'id_prefix': 'COMPANY_ISSUE_',
        }
    }

``class`` needs to reference the service-class object and ``class_init`` contains service specific
initialisation options. In this case you must tell the generic ``GitHubService`` class which kind of information
it shall deal with. Allowed are ``issue``, ``pr`` and ``commit``.

All other options are normal configuration options for the service, which are also available for the GitHub cloud
instance.

The need type and the ``github`` layout come with the built-in service, not with the class:
the example configures ``github-issues`` too, which is what adds the ``issue`` type and the ``github`` layout
that the needs of ``my-company-issues`` use.
A custom service alone gets neither, and its needs are refused with an ``Unknown need type 'issue'`` warning
that names the built-in service to configure:
configure the built-in service it imitates as well (``{}`` will do),
or declare the type in :ref:`needs_types` (and a ``github`` entry in :ref:`needs_layouts`).


Examples
--------

Commits
+++++++

**Search**
Search for all commits of Sphinx-Needs, which have ``Python`` in their message.

.. code-block:: rst

   .. needservice:: github-commits
      :query: repo:useblocks/sphinx-needs python
      :max_amount: 2

**Specific commit**

Document commit ``a4a596`` of **Sphinx-Needs**.

.. code-block:: rst

    .. needservice:: github-commits
       :specific: useblocks/sphinx-needs/a4a596


Filtering
+++++++++
Show all needs, which have ``github`` as part of their ``service`` value.

.. syntax-example::

    .. needtable::
       :filter: service is not None and 'github' in service
       :columns: id, title, type, service, user

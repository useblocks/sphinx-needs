.. _github_service:

GitHub services
===============

As GitHub provides different kinds of information (e.g. issues, prs or commits), there is a specialised service
for each information type:

+ ``github-issues``
+ ``github-prs``
+ ``github-commits``


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
All GitHub related services have a common set of configuration options
and their configuration must be done in :ref:`needs_services` inside the project's **conf.py** file.

:ref:`needs_services` must contain a key with the service name, e.g. ``github-issues``

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

Layout
++++++

The GitHub services are providing a new layout, called ``github``, which is used by default and is based on the
standard ``complete`` layout.

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

Need type
+++++++++
The GitHub services create 3 new need types: ``issue``, ``pr`` and ``commit``.
These types are used by default by the related service, but its usage can be overwritten in the service configuration
by setting ``need_type`` or in the directive directly by setting ``type``.

The configuration (names, colors, diagram representation) can also be overwritten by configuring your own need
type in the configuration. Simply use :ref:`needs_types` for this.

.. _service_github_custom:

Custom service
--------------
The preconfigured services ``github_issues``, ``github_prs`` and ``github_commits`` support the cloud instance of
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

.. code-block:: rst

    .. needtable::
       :filter: 'github' in service
       :columns: id, title, type, service, user

.. needtable::
   :filter: 'github' in service
   :columns: id, title, type, service, user

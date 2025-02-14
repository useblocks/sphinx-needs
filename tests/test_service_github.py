import json
from pathlib import Path

import pytest
import responses
from sphinx import version_info
from sphinx.util.console import strip_colors
from syrupy.filters import props


@responses.activate
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_service_github",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_build(test_app, snapshot):
    responses.get(
        "https://api.github.com/search/issues",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:useblocks/sphinx-needs is:issue", "per_page": "1"}
            )
        ],
        status=200,
        json=ISSUE_RESPONSE,
    )
    responses.get(
        "https://api.github.com/search/issues",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:useblocks/sphinx-needs is:pr", "per_page": "1"}
            )
        ],
        status=200,
        json=PR_RESPONSE,
    )
    responses.get(
        "https://api.github.com/search/commits",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:useblocks/sphinx-needs error ", "per_page": "1"}
            )
        ],
        status=200,
        json=COMMIT_RESPONSE,
    )
    responses.get(
        "https://api.github.com/repos/useblocks/sphinx-needs/commits/050bec750ff2c5acf881415fa2b5efb5fcce8414",
        status=200,
        json=COMMIT_SPECIFIC_RESPONSE,
    )
    responses.get(
        "https://api.github.com/repos/useblocks/sphinx-needs/commits/rate_limit",
        status=300,
        json={"message": "API rate limit exceeded"},
    )
    responses.get(
        "https://api.github.com/rate_limit",
        status=200,
        json={
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "reset": 1613414020}
            }
        },
    )
    responses.get(
        "https://avatars.githubusercontent.com/u/2997570",
        match=[responses.matchers.query_param_matcher({"v": "4"})],
        status=200,
        body=b"",
    )
    responses.get(
        "https://avatars.githubusercontent.com/in/29110",
        match=[responses.matchers.query_param_matcher({"v": "4"})],
        status=200,
        body=b"",
    )

    app = test_app
    app.build()
    warnings = strip_colors(app._warning.getvalue())
    # print(warnings)
    prefix = " [docutils]" if version_info >= (8, 0) else ""
    expected_warnings = [
        f'{Path(str(app.srcdir)) / "index.rst"}:4: WARNING: "query" or "specific" missing as option for github service. [needs.github]',
        f"{Path(str(app.srcdir)) / 'index.rst'}:23: WARNING: Bullet list ends without a blank line; unexpected unindent.{prefix}",
        f"{Path(str(app.srcdir)) / 'index.rst'}:22: WARNING: GitHub: API rate limit exceeded (twice). Stop here. [needs.github]",
    ]

    assert warnings.splitlines() == expected_warnings

    needs_data = json.loads((Path(app.outdir) / "needs.json").read_text("utf8"))
    assert needs_data == snapshot(
        exclude=props("created", "project", "avatar", "creator")
    )


ISSUE_RESPONSE = {
    "total_count": 518,
    "incomplete_results": False,
    "items": [
        {
            "url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1110",
            "repository_url": "https://api.github.com/repos/useblocks/sphinx-needs",
            "labels_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1110/labels{/name}",
            "comments_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1110/comments",
            "events_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1110/events",
            "html_url": "https://github.com/useblocks/sphinx-needs/issues/1110",
            "id": 2136385896,
            "node_id": "I_kwDOBHvbXc5_Vqlo",
            "number": 1110,
            "title": "needreport usage should count needs in post-process",
            "user": {
                "login": "chrisjsewell",
                "id": 2997570,
                "node_id": "MDQ6VXNlcjI5OTc1NzA=",
                "avatar_url": "https://avatars.githubusercontent.com/u/2997570?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/chrisjsewell",
                "html_url": "https://github.com/chrisjsewell",
                "followers_url": "https://api.github.com/users/chrisjsewell/followers",
                "following_url": "https://api.github.com/users/chrisjsewell/following{/other_user}",
                "gists_url": "https://api.github.com/users/chrisjsewell/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/chrisjsewell/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/chrisjsewell/subscriptions",
                "organizations_url": "https://api.github.com/users/chrisjsewell/orgs",
                "repos_url": "https://api.github.com/users/chrisjsewell/repos",
                "events_url": "https://api.github.com/users/chrisjsewell/events{/privacy}",
                "received_events_url": "https://api.github.com/users/chrisjsewell/received_events",
                "type": "User",
                "site_admin": False,
            },
            "labels": [
                {
                    "id": 491973814,
                    "node_id": "MDU6TGFiZWw0OTE5NzM4MTQ=",
                    "url": "https://api.github.com/repos/useblocks/sphinx-needs/labels/bug",
                    "name": "bug",
                    "color": "ee0701",
                    "default": True,
                    "description": None,
                }
            ],
            "state": "open",
            "locked": False,
            "assignee": {
                "login": "chrisjsewell",
                "id": 2997570,
                "node_id": "MDQ6VXNlcjI5OTc1NzA=",
                "avatar_url": "https://avatars.githubusercontent.com/u/2997570?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/chrisjsewell",
                "html_url": "https://github.com/chrisjsewell",
                "followers_url": "https://api.github.com/users/chrisjsewell/followers",
                "following_url": "https://api.github.com/users/chrisjsewell/following{/other_user}",
                "gists_url": "https://api.github.com/users/chrisjsewell/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/chrisjsewell/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/chrisjsewell/subscriptions",
                "organizations_url": "https://api.github.com/users/chrisjsewell/orgs",
                "repos_url": "https://api.github.com/users/chrisjsewell/repos",
                "events_url": "https://api.github.com/users/chrisjsewell/events{/privacy}",
                "received_events_url": "https://api.github.com/users/chrisjsewell/received_events",
                "type": "User",
                "site_admin": False,
            },
            "assignees": [
                {
                    "login": "chrisjsewell",
                    "id": 2997570,
                    "node_id": "MDQ6VXNlcjI5OTc1NzA=",
                    "avatar_url": "https://avatars.githubusercontent.com/u/2997570?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/chrisjsewell",
                    "html_url": "https://github.com/chrisjsewell",
                    "followers_url": "https://api.github.com/users/chrisjsewell/followers",
                    "following_url": "https://api.github.com/users/chrisjsewell/following{/other_user}",
                    "gists_url": "https://api.github.com/users/chrisjsewell/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/chrisjsewell/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/chrisjsewell/subscriptions",
                    "organizations_url": "https://api.github.com/users/chrisjsewell/orgs",
                    "repos_url": "https://api.github.com/users/chrisjsewell/repos",
                    "events_url": "https://api.github.com/users/chrisjsewell/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/chrisjsewell/received_events",
                    "type": "User",
                    "site_admin": False,
                }
            ],
            "milestone": None,
            "comments": 0,
            "created_at": "2024-02-15T12:19:11Z",
            "updated_at": "2024-02-15T12:19:30Z",
            "closed_at": None,
            "author_association": "MEMBER",
            "active_lock_reason": None,
            "body": "I've also just realised there is a bug in this directive:\r\n\r\nThe `usage` flag creates a count of user defined need types.\r\nHowever, it does this during the processing of the directive, rather than in a post-processing step.\r\nTherefore, the count will usually be incorrect.\r\n\r\n_Originally posted by @chrisjsewell in https://github.com/useblocks/sphinx-needs/issues/1105#issuecomment-1937172837_\r\n            ",
            "reactions": {
                "url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1110/reactions",
                "total_count": 0,
                "+1": 0,
                "-1": 0,
                "laugh": 0,
                "hooray": 0,
                "confused": 0,
                "heart": 0,
                "rocket": 0,
                "eyes": 0,
            },
            "timeline_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1110/timeline",
            "performed_via_github_app": None,
            "state_reason": None,
            "score": 1.0,
        }
    ],
}

PR_RESPONSE = {
    "total_count": 546,
    "incomplete_results": False,
    "items": [
        {
            "url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1112",
            "repository_url": "https://api.github.com/repos/useblocks/sphinx-needs",
            "labels_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1112/labels{/name}",
            "comments_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1112/comments",
            "events_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1112/events",
            "html_url": "https://github.com/useblocks/sphinx-needs/pull/1112",
            "id": 2137419108,
            "node_id": "PR_kwDOBHvbXc5nBjed",
            "number": 1112,
            "title": "👌 Capture `only` expressions for each need",
            "user": {
                "login": "chrisjsewell",
                "id": 2997570,
                "node_id": "MDQ6VXNlcjI5OTc1NzA=",
                "avatar_url": "https://avatars.githubusercontent.com/u/2997570?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/chrisjsewell",
                "html_url": "https://github.com/chrisjsewell",
                "followers_url": "https://api.github.com/users/chrisjsewell/followers",
                "following_url": "https://api.github.com/users/chrisjsewell/following{/other_user}",
                "gists_url": "https://api.github.com/users/chrisjsewell/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/chrisjsewell/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/chrisjsewell/subscriptions",
                "organizations_url": "https://api.github.com/users/chrisjsewell/orgs",
                "repos_url": "https://api.github.com/users/chrisjsewell/repos",
                "events_url": "https://api.github.com/users/chrisjsewell/events{/privacy}",
                "received_events_url": "https://api.github.com/users/chrisjsewell/received_events",
                "type": "User",
                "site_admin": False,
            },
            "labels": [],
            "state": "open",
            "locked": False,
            "assignee": None,
            "assignees": [],
            "milestone": None,
            "comments": 2,
            "created_at": "2024-02-15T20:45:12Z",
            "updated_at": "2024-02-15T20:55:43Z",
            "closed_at": None,
            "author_association": "MEMBER",
            "active_lock_reason": None,
            "draft": True,
            "pull_request": {
                "url": "https://api.github.com/repos/useblocks/sphinx-needs/pulls/1112",
                "html_url": "https://github.com/useblocks/sphinx-needs/pull/1112",
                "diff_url": "https://github.com/useblocks/sphinx-needs/pull/1112.diff",
                "patch_url": "https://github.com/useblocks/sphinx-needs/pull/1112.patch",
                "merged_at": None,
            },
            "body": '@David-Le-Nir and @danwos, as I explained in https://github.com/useblocks/sphinx-needs/issues/1103#issuecomment-1936305902, I think this is a better solution for handling need defined  within `only` directives.\r\n\r\nIn this first "read" phase, we simply just note all the parent `only` expressions of the need, storing them on an (optional) `only_expressions` field of the need data item.\r\n\r\nIf desired, in a subsequent "build" post-processing phase, called from the cached data (once per build), you could then evaluate the `only_expressions` and remove needs as a necessary (or do whatever).\r\nThis logic would go here: https://github.com/useblocks/sphinx-needs/blob/84a5f72f2e72ab1471ab2d1bb5c570d6115ef199/sphinx_needs/directives/need.py#L385\r\n\r\nthis is more in-line with the logic of the `only` directive, where everything is cached and parts of the doctree are only removed during the build phase.\r\n\r\nwould supercede #1106 \r\n\r\ncloses #1103',
            "reactions": {
                "url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1112/reactions",
                "total_count": 0,
                "+1": 0,
                "-1": 0,
                "laugh": 0,
                "hooray": 0,
                "confused": 0,
                "heart": 0,
                "rocket": 0,
                "eyes": 0,
            },
            "timeline_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/1112/timeline",
            "performed_via_github_app": None,
            "state_reason": None,
            "score": 1.0,
        }
    ],
}

COMMIT_RESPONSE = {
    "total_count": 23,
    "incomplete_results": False,
    "items": [
        {
            "url": "https://api.github.com/repos/useblocks/sphinx-needs/commits/6abd389369c5bbd5216f5ecdc3da1323ebe8620d",
            "sha": "6abd389369c5bbd5216f5ecdc3da1323ebe8620d",
            "node_id": "MDY6Q29tbWl0NzUyMjU5NDk6NmFiZDM4OTM2OWM1YmJkNTIxNmY1ZWNkYzNkYTEzMjNlYmU4NjIwZA==",
            "html_url": "https://github.com/useblocks/sphinx-needs/commit/6abd389369c5bbd5216f5ecdc3da1323ebe8620d",
            "comments_url": "https://api.github.com/repos/useblocks/sphinx-needs/commits/6abd389369c5bbd5216f5ecdc3da1323ebe8620d/comments",
            "commit": {
                "url": "https://api.github.com/repos/useblocks/sphinx-needs/git/commits/6abd389369c5bbd5216f5ecdc3da1323ebe8620d",
                "author": {
                    "date": "2024-02-12T08:36:07.000Z",
                    "name": "Chris Sewell",
                    "email": "chrisj_sewell@hotmail.com",
                },
                "committer": {
                    "date": "2024-02-12T09:36:07.000+01:00",
                    "name": "GitHub",
                    "email": "noreply@github.com",
                },
                "message": '🧪 Add test for `needreport` directive (#1105)\n\nCurrently there is no test for this directive, this PR adds one.\r\n\r\nThis PR also fixes the directive:\r\n\r\n- Make the options flags\r\n- Change errors in the directive to emit warnings, rather than excepting\r\nthe whole build\r\n- Allow for `template` to be specified as a directive option\r\n- Allow the the `dropdown` directive used in the default template, which\r\nrequires an external sphinx extension, to be overriden using\r\n`needs_render_context = {"report_directive": "admonition"}` (I left the\r\ndefault as `dropdown`, so as not to introduce a breaking change)',
                "tree": {
                    "url": "https://api.github.com/repos/useblocks/sphinx-needs/git/trees/f4d12ed387505ee76d69c9f7ef43d3a1008d3edd",
                    "sha": "f4d12ed387505ee76d69c9f7ef43d3a1008d3edd",
                },
                "comment_count": 0,
            },
            "author": {
                "login": "chrisjsewell",
                "id": 2997570,
                "node_id": "MDQ6VXNlcjI5OTc1NzA=",
                "avatar_url": "https://avatars.githubusercontent.com/u/2997570?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/chrisjsewell",
                "html_url": "https://github.com/chrisjsewell",
                "followers_url": "https://api.github.com/users/chrisjsewell/followers",
                "following_url": "https://api.github.com/users/chrisjsewell/following{/other_user}",
                "gists_url": "https://api.github.com/users/chrisjsewell/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/chrisjsewell/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/chrisjsewell/subscriptions",
                "organizations_url": "https://api.github.com/users/chrisjsewell/orgs",
                "repos_url": "https://api.github.com/users/chrisjsewell/repos",
                "events_url": "https://api.github.com/users/chrisjsewell/events{/privacy}",
                "received_events_url": "https://api.github.com/users/chrisjsewell/received_events",
                "type": "User",
                "site_admin": False,
            },
            "committer": {
                "login": "web-flow",
                "id": 19864447,
                "node_id": "MDQ6VXNlcjE5ODY0NDQ3",
                "avatar_url": "https://avatars.githubusercontent.com/u/19864447?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/web-flow",
                "html_url": "https://github.com/web-flow",
                "followers_url": "https://api.github.com/users/web-flow/followers",
                "following_url": "https://api.github.com/users/web-flow/following{/other_user}",
                "gists_url": "https://api.github.com/users/web-flow/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/web-flow/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/web-flow/subscriptions",
                "organizations_url": "https://api.github.com/users/web-flow/orgs",
                "repos_url": "https://api.github.com/users/web-flow/repos",
                "events_url": "https://api.github.com/users/web-flow/events{/privacy}",
                "received_events_url": "https://api.github.com/users/web-flow/received_events",
                "type": "User",
                "site_admin": False,
            },
            "parents": [
                {
                    "url": "https://api.github.com/repos/useblocks/sphinx-needs/commits/73b961e29583bc0ac8892ef9c4e2bfb75f7f46bb",
                    "html_url": "https://github.com/useblocks/sphinx-needs/commit/73b961e29583bc0ac8892ef9c4e2bfb75f7f46bb",
                    "sha": "73b961e29583bc0ac8892ef9c4e2bfb75f7f46bb",
                }
            ],
            "repository": {
                "id": 75225949,
                "node_id": "MDEwOlJlcG9zaXRvcnk3NTIyNTk0OQ==",
                "name": "sphinx-needs",
                "full_name": "useblocks/sphinx-needs",
                "private": False,
                "owner": {
                    "login": "useblocks",
                    "id": 998587,
                    "node_id": "MDEyOk9yZ2FuaXphdGlvbjk5ODU4Nw==",
                    "avatar_url": "https://avatars.githubusercontent.com/u/998587?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/useblocks",
                    "html_url": "https://github.com/useblocks",
                    "followers_url": "https://api.github.com/users/useblocks/followers",
                    "following_url": "https://api.github.com/users/useblocks/following{/other_user}",
                    "gists_url": "https://api.github.com/users/useblocks/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/useblocks/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/useblocks/subscriptions",
                    "organizations_url": "https://api.github.com/users/useblocks/orgs",
                    "repos_url": "https://api.github.com/users/useblocks/repos",
                    "events_url": "https://api.github.com/users/useblocks/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/useblocks/received_events",
                    "type": "Organization",
                    "site_admin": False,
                },
                "html_url": "https://github.com/useblocks/sphinx-needs",
                "description": "Adds needs/requirements to sphinx",
                "fork": False,
                "url": "https://api.github.com/repos/useblocks/sphinx-needs",
                "forks_url": "https://api.github.com/repos/useblocks/sphinx-needs/forks",
                "keys_url": "https://api.github.com/repos/useblocks/sphinx-needs/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/useblocks/sphinx-needs/collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/useblocks/sphinx-needs/teams",
                "hooks_url": "https://api.github.com/repos/useblocks/sphinx-needs/hooks",
                "issue_events_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/events{/number}",
                "events_url": "https://api.github.com/repos/useblocks/sphinx-needs/events",
                "assignees_url": "https://api.github.com/repos/useblocks/sphinx-needs/assignees{/user}",
                "branches_url": "https://api.github.com/repos/useblocks/sphinx-needs/branches{/branch}",
                "tags_url": "https://api.github.com/repos/useblocks/sphinx-needs/tags",
                "blobs_url": "https://api.github.com/repos/useblocks/sphinx-needs/git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/useblocks/sphinx-needs/git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/useblocks/sphinx-needs/git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/useblocks/sphinx-needs/git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/useblocks/sphinx-needs/statuses/{sha}",
                "languages_url": "https://api.github.com/repos/useblocks/sphinx-needs/languages",
                "stargazers_url": "https://api.github.com/repos/useblocks/sphinx-needs/stargazers",
                "contributors_url": "https://api.github.com/repos/useblocks/sphinx-needs/contributors",
                "subscribers_url": "https://api.github.com/repos/useblocks/sphinx-needs/subscribers",
                "subscription_url": "https://api.github.com/repos/useblocks/sphinx-needs/subscription",
                "commits_url": "https://api.github.com/repos/useblocks/sphinx-needs/commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/useblocks/sphinx-needs/git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/useblocks/sphinx-needs/comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/useblocks/sphinx-needs/contents/{+path}",
                "compare_url": "https://api.github.com/repos/useblocks/sphinx-needs/compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/useblocks/sphinx-needs/merges",
                "archive_url": "https://api.github.com/repos/useblocks/sphinx-needs/{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/useblocks/sphinx-needs/downloads",
                "issues_url": "https://api.github.com/repos/useblocks/sphinx-needs/issues{/number}",
                "pulls_url": "https://api.github.com/repos/useblocks/sphinx-needs/pulls{/number}",
                "milestones_url": "https://api.github.com/repos/useblocks/sphinx-needs/milestones{/number}",
                "notifications_url": "https://api.github.com/repos/useblocks/sphinx-needs/notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/useblocks/sphinx-needs/labels{/name}",
                "releases_url": "https://api.github.com/repos/useblocks/sphinx-needs/releases{/id}",
                "deployments_url": "https://api.github.com/repos/useblocks/sphinx-needs/deployments",
            },
            "score": 1.0,
        }
    ],
}


COMMIT_SPECIFIC_RESPONSE = {
    "sha": "050bec750ff2c5acf881415fa2b5efb5fcce8414",
    "node_id": "C_kwDOBHvbXdoAKDA1MGJlYzc1MGZmMmM1YWNmODgxNDE1ZmEyYjVlZmI1ZmNjZTg0MTQ",
    "commit": {
        "author": {
            "name": "dependabot[bot]",
            "email": "49699333+dependabot[bot]@users.noreply.github.com",
            "date": "2024-02-15T14:04:06Z",
        },
        "committer": {
            "name": "GitHub",
            "email": "noreply@github.com",
            "date": "2024-02-15T14:04:06Z",
        },
        "message": "Bump actions/cache from 3 to 4 (#1092)\n\nCo-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>",
        "tree": {
            "sha": "6e20d545a52e6a170af2e2db345401a423213490",
            "url": "https://api.github.com/repos/useblocks/sphinx-needs/git/trees/6e20d545a52e6a170af2e2db345401a423213490",
        },
        "url": "https://api.github.com/repos/useblocks/sphinx-needs/git/commits/050bec750ff2c5acf881415fa2b5efb5fcce8414",
        "comment_count": 0,
        "verification": {
            "verified": True,
            "reason": "valid",
            "signature": "-----BEGIN PGP SIGNATURE-----\n\nwsFcBAABCAAQBQJlzhnWCRC1aQ7uu5UhlAAAMvAQAJpZeW/31DvZUWOnGealNbCG\n7ciH6HtEKivPr69a44ce03zkU4tsgIAhDJu5JxpiT5FUJ2oiTfO3PNnkqiJZmpCk\nawTb1bJpXbXOFQ6vpYz78N0lZXgoasigP6hfikRTlW5ZNWzg07u+PjJEGf9ogdAA\nzrxkrnx1g4O/Aj0iAh9mnX3AhByR1iefCatMSq+3oZfqM2YtkWv+LHqYoOO8ZvoA\nzHxJky0B5EA3hWu9v+6yVt6W0E3Ozq+FzmhAGEwRcTz5PVjQd/luQvis1o1k18ai\nPdqBxoIl3+tWMTceU/0KLgU8KwGyfJFDj0dmnMuEyCFlQvMro4JNPnbOea6dK3ei\nRXPB3wkhUbDm/NRKI71zG0fbHkBpvme01t1MsDA5E0qmIhtwdDfQ50ME24oa7/vv\nr7Deg6+rSpS+VgshuhoOXT/ILKwK7oU1igBfzw+QscyOfgfQRelTiuayEkJzAwzf\n1jJOhRNbJNmXAnbgvbEDIW+/YoioJiDZotTCM1Jz785RXyqwuFO9+8b8jsS2GYYP\noyLVl10DhMGeAKfEFLyUZS8VIVO4u+w4hzTWIGT2CdmO9u7gjdnAcOE0v33MCr2+\npp9j9jo6ivvaZtNWObnmG9tcB6iH4MfRNPmY18ppNHG9ZXFOsOJr8bDcz/qbMioQ\nGQnUiu5KWiD87NrdhuCo\n=DIHs\n-----END PGP SIGNATURE-----\n",
            "payload": "tree 6e20d545a52e6a170af2e2db345401a423213490\nparent a85d49be05949424e38c08233871f32064075828\nauthor dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com> 1708005846 +0100\ncommitter GitHub <noreply@github.com> 1708005846 +0100\n\nBump actions/cache from 3 to 4 (#1092)\n\nCo-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>\r\n",
        },
    },
    "url": "https://api.github.com/repos/useblocks/sphinx-needs/commits/050bec750ff2c5acf881415fa2b5efb5fcce8414",
    "html_url": "https://github.com/useblocks/sphinx-needs/commit/050bec750ff2c5acf881415fa2b5efb5fcce8414",
    "comments_url": "https://api.github.com/repos/useblocks/sphinx-needs/commits/050bec750ff2c5acf881415fa2b5efb5fcce8414/comments",
    "author": {
        "login": "dependabot[bot]",
        "id": 49699333,
        "node_id": "MDM6Qm90NDk2OTkzMzM=",
        "avatar_url": "https://avatars.githubusercontent.com/in/29110?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/dependabot%5Bbot%5D",
        "html_url": "https://github.com/apps/dependabot",
        "followers_url": "https://api.github.com/users/dependabot%5Bbot%5D/followers",
        "following_url": "https://api.github.com/users/dependabot%5Bbot%5D/following{/other_user}",
        "gists_url": "https://api.github.com/users/dependabot%5Bbot%5D/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/dependabot%5Bbot%5D/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/dependabot%5Bbot%5D/subscriptions",
        "organizations_url": "https://api.github.com/users/dependabot%5Bbot%5D/orgs",
        "repos_url": "https://api.github.com/users/dependabot%5Bbot%5D/repos",
        "events_url": "https://api.github.com/users/dependabot%5Bbot%5D/events{/privacy}",
        "received_events_url": "https://api.github.com/users/dependabot%5Bbot%5D/received_events",
        "type": "Bot",
        "site_admin": False,
    },
    "committer": {
        "login": "web-flow",
        "id": 19864447,
        "node_id": "MDQ6VXNlcjE5ODY0NDQ3",
        "avatar_url": "https://avatars.githubusercontent.com/u/19864447?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/web-flow",
        "html_url": "https://github.com/web-flow",
        "followers_url": "https://api.github.com/users/web-flow/followers",
        "following_url": "https://api.github.com/users/web-flow/following{/other_user}",
        "gists_url": "https://api.github.com/users/web-flow/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/web-flow/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/web-flow/subscriptions",
        "organizations_url": "https://api.github.com/users/web-flow/orgs",
        "repos_url": "https://api.github.com/users/web-flow/repos",
        "events_url": "https://api.github.com/users/web-flow/events{/privacy}",
        "received_events_url": "https://api.github.com/users/web-flow/received_events",
        "type": "User",
        "site_admin": False,
    },
    "parents": [
        {
            "sha": "a85d49be05949424e38c08233871f32064075828",
            "url": "https://api.github.com/repos/useblocks/sphinx-needs/commits/a85d49be05949424e38c08233871f32064075828",
            "html_url": "https://github.com/useblocks/sphinx-needs/commit/a85d49be05949424e38c08233871f32064075828",
        }
    ],
    "stats": {"total": 4, "additions": 2, "deletions": 2},
    "files": [
        {
            "sha": "4efe5c00a0c11788bfba0fe3081d7f456559178d",
            "filename": ".github/workflows/benchmark.yaml",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "blob_url": "https://github.com/useblocks/sphinx-needs/blob/050bec750ff2c5acf881415fa2b5efb5fcce8414/.github%2Fworkflows%2Fbenchmark.yaml",
            "raw_url": "https://github.com/useblocks/sphinx-needs/raw/050bec750ff2c5acf881415fa2b5efb5fcce8414/.github%2Fworkflows%2Fbenchmark.yaml",
            "contents_url": "https://api.github.com/repos/useblocks/sphinx-needs/contents/.github%2Fworkflows%2Fbenchmark.yaml?ref=050bec750ff2c5acf881415fa2b5efb5fcce8414",
            "patch": "@@ -22,7 +22,7 @@ jobs:\n         run: pytest --benchmark-json output.json -k _time tests/benchmarks\n \n       - name: Download previous benchmark data\n-        uses: actions/cache@v3\n+        uses: actions/cache@v4\n         with:\n           path: ./cache\n           key: ${{ runner.os }}-benchmark",
        },
        {
            "sha": "bf7070bc9ca51449263ef73d2d3da384438df37a",
            "filename": ".github/workflows/js_test.yml",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "blob_url": "https://github.com/useblocks/sphinx-needs/blob/050bec750ff2c5acf881415fa2b5efb5fcce8414/.github%2Fworkflows%2Fjs_test.yml",
            "raw_url": "https://github.com/useblocks/sphinx-needs/raw/050bec750ff2c5acf881415fa2b5efb5fcce8414/.github%2Fworkflows%2Fjs_test.yml",
            "contents_url": "https://api.github.com/repos/useblocks/sphinx-needs/contents/.github%2Fworkflows%2Fjs_test.yml?ref=050bec750ff2c5acf881415fa2b5efb5fcce8414",
            "patch": "@@ -23,7 +23,7 @@ jobs:\n       run: |\n         echo \"dir=$(pip cache dir)\" >> $GITHUB_OUTPUT\n     - name: Pip cache\n-      uses: actions/cache@v3\n+      uses: actions/cache@v4\n       with:\n         path: ${{ steps.pip-cache.outputs.dir }}\n         key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}",
        },
    ],
}

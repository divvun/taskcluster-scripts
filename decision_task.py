"""
This file contains the decision task code for divvun's CI. It is in charge of
creating all of the other tasks for a repository's CI. It should always be the
only thing called from a `.taskcluster.yml`, if you need new tasks, add them
here in the right section.
"""
import os
import os.path
import decisionlib
from decisionlib import CONFIG
from tasks import *


def tasks(task_for: str):
    # Work around a tc-github bug/limitation:
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1548781#c4
    if task_for.startswith("github"):
        # https://github.com/taskcluster/taskcluster/blob/21f257dc8/services/github/config.yml#L14
        CONFIG.routes_for_all_subtasks.append("statuses")

    if task_for == "github-pull-request":
        CONFIG.index_read_only = True
        # We want the merge commit that GitHub creates for the PR.
        # The event does contain a `pull_request.merge_commit_sha` key, but it is wrong:
        # https://github.com/servo/servo/pull/22597#issuecomment-451518810
        CONFIG.git_sha_is_current_head()

        # As of right now we do not want to run any task for pull requests. Add
        # them here if needed. Keep in mind that said task should not have
        # access to any secrets.
        return

    if task_for == "daily":
        # Put any daily task here.
        return

    repo_name = os.environ["REPO_NAME"]

    is_tag = False
    tag_name = ""
    if CONFIG.git_ref.startswith("refs/tags/"):
        tag_name = CONFIG.git_ref[len("refs/tags/"):]
        is_tag = True


    # Lang repositories common tasks
    if repo_name.startswith("lang-"):
        lang_task_id = create_lang_task(repo_name.endswith("apertium"))
        for os_, type_ in [
            ("macos-latest", "speller-macos"),
            ("macos-latest", "speller-mobile"),
            ("windows-latest", "speller-windows"),
        ]:
            create_bundle_task(os_, type_, lang_task_id)

    # Keyboard repositories common tasks
    if repo_name.startswith("keyboard-"):
        for os_ in {"windows-latest", "macos-latest"}:
            create_kbd_task(os_)

    # pahkat-reposrv tasks
    if repo_name == "pahkat-reposrv":
        build_task_id = create_pahkat_reposrv_task(tag_name) # TODO: check if is tag
        if is_tag:
            release_task_id = create_pahkat_reposrv_release_task(build_task_id, tag_name)
            create_ansible_task(["pahkat-reposrv"], depends_on=release_task_id)

    if repo_name == "pahkat":
        create_pahkat_tasks()

    # Deployment tasks
    if repo_name == "ansible-playbooks":
        create_ansible_task(["setup", "pahkat-reposrv"])


task_for = os.environ["TASK_FOR"]
with decisionlib.make_repo_bundle("/ci", "ci.bundle", "HEAD"):
    assert CONFIG.git_sha, "Unknown git sha for current repo"
    with decisionlib.make_repo_bundle("/repo", "repo.bundle", CONFIG.git_sha):
        tasks(task_for)

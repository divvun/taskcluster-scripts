# coding: utf8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import os.path
import decisionlib
from decisionlib import CONFIG, SHARED
from tasks import create_lang_task, create_bundle_task


def tasks(task_for):
    if CONFIG.git_ref.startswith("refs/heads/"):
        branch = CONFIG.git_ref[len("refs/heads/") :]

    # Work around a tc-github bug/limitation:
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1548781#c4
    if task_for.startswith("github"):
        # https://github.com/taskcluster/taskcluster/blob/21f257dc8/services/github/config.yml#L14
        CONFIG.routes_for_all_subtasks.append("statuses")

    if task_for == "github-pull-request":
        CONFIG.index_read_only = True
        CONFIG.docker_image_build_worker_type = None
        # We want the merge commit that GitHub creates for the PR.
        # The event does contain a `pull_request.merge_commit_sha` key, but it is wrong:
        # https://github.com/servo/servo/pull/22597#issuecomment-451518810
        CONFIG.git_sha_is_current_head()
    elif task_for == "daily":
        pass

    repo_name = os.environ["REPO_NAME"]
    if repo_name.startswith("lang-"):
        lang_task_id = create_lang_task(repo_name.endswith("apertium"))
        #lang_task_id=None
        for os_, type_ in (("macos-latest", "speller-macos"), ("macos-latest", "speller-mobile"), ("windows-latest", "speller-windows")):
            create_bundle_task(os_, type_, lang_task_id)


build_dependencies_artifacts_expire_in = "1 month"
log_artifacts_expire_in = "1 year"

CONFIG.task_name_template = "Divvun: %s"
CONFIG.docker_images_expire_in = build_dependencies_artifacts_expire_in
CONFIG.repacked_msi_files_expire_in = build_dependencies_artifacts_expire_in
CONFIG.index_prefix = "project.divvun"
CONFIG.default_provisioner_id = "test"
CONFIG.docker_image_build_worker_type = "docker"

task_for = os.environ["TASK_FOR"]
with decisionlib.make_repo_bundle("/ci", "ci.bundle", 'HEAD'):
    with decisionlib.make_repo_bundle("/repo", "repo.bundle", CONFIG.git_sha):
        tasks(task_for)

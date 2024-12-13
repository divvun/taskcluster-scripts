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
from typing import Set, Any
from taskcluster import helper


SECRETS: Set[str] = set()
_ORIG_PRINT = print

def filtered_print(*args):
    """
    This function is designed to replace the original print function to avoid
    accidental secret leaks. It'll replace all secrets contained in the
    `SECRETS` global variable with `[*******]`.
    """
    filtered = []
    for arg in args:
        for secret in SECRETS:
            arg = str(arg).replace(secret, "[******]")
        filtered.append(arg)
    try:
        _ORIG_PRINT(*filtered)
    except UnicodeEncodeError:
        _ORIG_PRINT("[Unicode decode error]")


print = filtered_print


def gather_secrets():
    """
    Gather all available secrets from taskcluster and put them into the global
    `SECRETS` variable. This should be called quite early to avoid accidental
    secrets leaking.
    """
    secrets_service = helper.TaskclusterConfig().get_service("secrets")
    secret_names: Set[str] = set()

    def get_values_from_json(obj: Any) -> Set[str]:
        """
        Returns a list of values contained in a JSON object by recursively traversing it.
        """
        out = set()

        def flatten(x):
            if isinstance(x, dict):
                for value in x.values():
                    flatten(value)
            elif isinstance(x, list):
                for value in x:
                    flatten(value)
            else:
                out.add(x)

        flatten(obj)
        return out

    continuation = None
    while True:
        res = secrets_service.list(continuationToken=continuation)
        secret_names.update(set(res["secrets"]))
        if not res.get("continuationToken"):
            break
        continuation = res["continuationToken"]

    for name in secret_names:
        try:
            res = secrets_service.get(name)
            SECRETS.update(get_values_from_json(res["secret"]))
        except:
            # This happens when we're not allowed to read the secret. Unfortunately
            # there's no way of filtering out secrets we can't read from the
            # listing so we have to try to get them all.
            pass


def tasks(task_for: str):
    print("ON BRANCH: private-repos") # TODO: remove when done testing
    repo_name = os.environ["REPO_NAME"]
    if "[ci skip]" in CONFIG.commit_message:
        print("Skipping CI")
        return

    if task_for == "github-pull-request":
        CONFIG.index_read_only = True
        # We want the merge commit that GitHub creates for the PR.
        # The event does contain a `pull_request.merge_commit_sha` key, but it is wrong:
        # https://github.com/servo/servo/pull/22597#issuecomment-451518810
        CONFIG.git_sha_is_current_head()

        # As of right now we do not want to run any task for pull requests. Add
        # them here if needed. Keep in mind that said task should not have
        # access to any secrets.
        # Lang repositories common tasks
        if repo_name.startswith("lang-"):
            create_lang_tasks(repo_name)

        if repo_name == "gut":
            create_gut_tasks()

        return

    if task_for == "refresh_mso_patches":
        create_mso_patch_gen_task()
        return

    if task_for == "clean_mirrors":
        create_mirror_cleanup_task()
        return

    is_tag = False
    tag_name = ""
    if CONFIG.git_ref.startswith("refs/tags/"):
        tag_name = CONFIG.git_ref[len("refs/tags/") :]
        is_tag = True

    # Lang repositories common tasks
    if repo_name.startswith("lang-"):
        create_lang_tasks(repo_name)

    # Keyboard repositories common tasks
    if repo_name.startswith("keyboard-"):
        create_kbd_tasks()

    # pahkat-reposrv tasks
    if repo_name == "pahkat-reposrv":
        build_task_id = create_pahkat_reposrv_task(tag_name)  # TODO: check if is tag
        if is_tag:
            release_task_id = create_pahkat_reposrv_release_task(
                build_task_id, tag_name
            )
            create_ansible_task(["pahkat-reposrv"], depends_on=release_task_id)

    if repo_name == "pahkat":
        create_pahkat_tasks()

    if repo_name == "divvun-manager-macos":
        create_divvun_manager_macos_task()

    if repo_name == "divvun-manager-windows":
        create_divvun_manager_windows_tasks()

    # Deployment tasks
    if repo_name == "ansible-playbooks":
        create_ansible_task(["setup", "pahkat-reposrv"])

    if repo_name == "divvunspell-libreoffice":
        create_libreoffice_tasks()

    if repo_name == "spelli":
        create_spelli_task()

    if repo_name == "windivvun-service":
        create_windivvun_tasks()

    if repo_name == "divvun-keyboard":
        create_divvun_keyboard_tasks("divvun.kbdgen", is_dev=False)

    if repo_name == "divvun-dev-keyboard":
        create_divvun_keyboard_tasks("divvun-dev.kbdgen", is_dev=True)

    if repo_name == "gut":
        create_gut_tasks()

    if repo_name == "kbdi":
        create_kbdi_tasks()

    if repo_name == "kbdgen":
        create_kbdgen_tasks()

    if repo_name == "divvunspell":
        create_divvunspell_tasks()

    if repo_name == "divvun-omegat-poc":
        create_omegat_tasks()

    if repo_name == "mso-nda-resources":
        create_mso_resources_tasks()

    if repo_name == "macdivvun-service":
        create_macdivvun_task()


gather_secrets()

task_for = os.environ["TASK_FOR"]
repo_name = os.environ["REPO_NAME"]

assert CONFIG.git_sha, "Unknown git sha for current repo"
tasks(task_for)

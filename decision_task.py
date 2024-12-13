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
from runner import gather_secrets

gather_secrets()

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


task_for = os.environ["TASK_FOR"]
repo_name = os.environ["REPO_NAME"]

assert CONFIG.git_sha, "Unknown git sha for current repo"
tasks(task_for)

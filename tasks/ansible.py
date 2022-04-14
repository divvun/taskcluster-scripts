from typing import List
from decisionlib import CONFIG

from .common import linux_build_task


def create_ansible_task(roles: List[str], depends_on=None):
    task = (
        linux_build_task(
            "Ansible playbooks deployment: {}".format(",".join(roles)),
            with_secrets=False,
            clone_self=False,
        )
        .with_scopes("secrets:get:divvun-deploy")
        .with_additional_repo(
            "https://github.com/divvun/ansible-playbooks.git", "playbooks"
        )
        .with_script("cd playbooks")
        .with_script(
            "`python3 ${HOME}/tasks/${TASK_ID}/ci/setup_ansible_secrets.py divvun-deploy`"
        )
        .with_script("chmod 700 tmp/id_ed25519")
        .with_script("apt-get install -y ansible")
        .with_env(ANSIBLE_HOST_KEY_CHECKING="false")
        .with_script(
            "ansible all -u root --private-key tmp/id_ed25519 -m include_role "
            + " ".join(("-a name={}".format(role) for role in roles))
            + " -i ${HOST},"
        )
    )

    if depends_on is not None:
        task = task.with_dependencies(depends_on)

    return task.find_or_create(f"deploy.{CONFIG.index_path}")

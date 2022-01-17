from decisionlib import CONFIG
from gha import GithubAction

from .common import linux_build_task


def create_pahkat_task(is_tag: bool):
    task = (linux_build_task("Pahkat reposrv build", with_secrets=False)
        .with_gha(
            "Install rust",
            GithubAction(
                "actions-rs/toolchain", {"components": "rustfmt", "toolchain": "stable", "override": True}
            ),
        )
        .with_gha(
            "Build pahkat reposrv",
            GithubAction(
                "actions-rs/cargo", {"command": "build" if is_tag else "check", "args": "--release" if is_tag else ""}
            ),
        )
        .with_prep_gha_tasks()
    )

    if is_tag:
        task = (task
            .with_script("cp ./target/release/pahkat-reposrv /")
            .with_artifacts("/pahkat-reposrv")
        )

    return task.find_or_create(f"build.linux_x64.{CONFIG.git_sha}")

def create_pahkat_release_task(build_task_id: str, tag_name: str):
    return (linux_build_task("Pahkat reposrv release")
        .with_curl_artifact_script(build_task_id, "pahkat-reposrv")
        .with_gha(
            "Release pahkat reposrv",
            GithubAction(
                "softprops/action-gh-release", {"tag_name": tag_name, "files": "pahkat-reposrv"}
            ).with_secret_input("token", "divvun", "github.token")
        )
        .with_prep_gha_tasks()
        .find_or_create(f"release.linux_x64.{CONFIG.git_sha}"))

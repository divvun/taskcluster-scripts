from decisionlib import CONFIG
from gha import GithubAction

from .common import linux_build_task


def create_pahkat_task(tag_name: str):
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
                "actions-rs/cargo", {"command": "build" if tag_name else "check", "args": "--release" if tag_name else ""}
            ),
        )
        .with_prep_gha_tasks()
    )

    if tag_name:
        task = (task
            .with_script("cp ./target/release/pahkat-reposrv /")
            .with_artifacts("/pahkat-reposrv")
        )

        return task.find_or_create(f"build.linux_x64.{tag_name}")
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

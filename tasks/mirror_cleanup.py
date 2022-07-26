from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import (
    linux_build_task,
    gha_setup,
    gha_pahkat,
    PAHKAT_REPO,
    NIGHTLY_CHANNEL,
    generic_rust_build_upload_task,
    RUST_ENV,
)


def create_mirror_cleanup_task():
    return (
        linux_build_task("Cleanup pahkat mirrors")
        .with_scopes("secrets:get:divvun-deploy")
        .with_gha("setup_git", GithubActionScript("""
            git config user.email "feedback@divvun.no"
            git config user.name "divvunbot"
        """))
        .with_script(
            "cd ~/ && `python3 ${HOME}/tasks/${TASK_ID}/ci/setup_ansible_secrets.py divvun-deploy`"
        )
        .with_script("mkdir ~/.ssh && chmod 700 ~/.ssh && mv tmp/id_ed25519 ~/.ssh && chmod 600 ~/.ssh/id_ed25519")
        .with_additional_repo(
            "https://github.com/divvun/pahkat", "pahkat"
        )
        .with_script("ssh-keyscan github.com")
        .with_additional_repo(
            "git@github.com:kivvun/pahkat.uit.no-index", "index"
        )
        .with_script("cd repo && git pull origin main")
        .find_or_create(f"cleanup.pahkat.uit.no.{CONFIG.index_path}")
    )

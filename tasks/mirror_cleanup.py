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
        linux_build_task("Cleanup pahkat mirrors", clone_self=False)
        .with_scopes("secrets:get:divvun-deploy")
        .with_script(
            "cd ~/ && `python3 ${HOME}/tasks/${TASK_ID}/ci/setup_ansible_secrets.py divvun-deploy`"
        )
        .with_script("mkdir ~/.ssh && chmod 700 ~/.ssh && mv tmp/id_ed25519 ~/.ssh && chmod 600 ~/.ssh/id_ed25519")
        .with_script("ssh-keyscan github.com pahkat.uit.no > ~/.ssh/known_hosts")
        .with_additional_repo(
            "https://github.com/divvun/pahkat", "pahkat"
        )
        .with_additional_repo(
            "git@github.com:divvun/pahkat.uit.no-index", "index"
        )
        .with_gha(
            "Set CWD",
            GithubActionScript(f"echo ::set-cwd::$HOME/pahkat"),
        )
        .with_gha("setup_git", GithubActionScript("""
            git config user.email "feedback@divvun.no"
            git config user.name "divvunbot"
        """))
        .with_gha(
            "install_rust",
            GithubAction(
                "actions-rs/toolchain",
                {
                    "toolchain": "stable",
                    "profile": "minimal",
                    "override": "true",
                },
            ),
        )
        .with_gha(
            "build",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": f"--release --verbose -p pahkat-repomgr",
                },
            ),
        )
        .with_script("ssh root@pahkat.uit.no systemctl stop pahkat-reposrv", as_gha=True)
        .with_gha("nuke_nighlies", GithubActionScript(
            """
            cd /root/index
            git pull origin main
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./main
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./tools
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./divvun-installer
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./devtools
            git commit -a -m "[CI] Cleanup old nightlies"
            git push origin main
            """
        ))
        .with_script("ssh root@pahkat.uit.no \"cd /pahkat-index && sudo -u pahkat-reposrv git pull\"", as_gha=True)
        .with_script("ssh root@pahkat.uit.no systemctl start pahkat-reposrv", as_gha=True)
        .with_gha("restart", GithubActionScript("sleep 2 && ssh root@pahkat.uit.no systemctl restart pahkat-reposrv", is_post=True))
        .find_or_create(f"cleanup.pahkat.uit.no.{CONFIG.index_path}")
    )

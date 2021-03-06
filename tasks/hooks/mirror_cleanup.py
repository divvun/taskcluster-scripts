from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from ..common import (
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
            "cd ~/ && `python3 ${HOME}/tasks/${TASK_ID}/ci/scripts/setup_ansible_secrets.py divvun-deploy`"
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
        .with_gha("nuke_nightlies", GithubActionScript(
            """
            cd /root/index
            git config user.email "feedback@divvun.no"
            git config user.name "divvunbot"
            git pull origin main
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./main
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./tools
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./divvun-installer
            /root/pahkat/target/release/repomgr nuke package nightlies -k 5 -r ./devtools
            git commit -a -m "[CI] Cleanup old nightlies" || exit 0
            git push origin main
            """, post_script="sleep 2 && ssh root@pahkat.uit.no systemctl restart pahkat-reposrv"
        ))
        .with_script("ssh root@pahkat.uit.no \"cd /pahkat-index && sudo -u pahkat-reposrv git pull\"", as_gha=True)
        .with_script("ssh root@pahkat.uit.no systemctl start pahkat-reposrv", as_gha=True)
        .with_gha("clean_bucket", GithubActionScript("""
            pip3 install boto3 toml
            cd /root/index
            python3 /root/tasks/${TASK_ID}/ci/scripts/clean_pahkat_repos.py
        """).with_env("S3_REGION", "ams3").with_env("S3_ENDPOINT", "https://ams3.digitaloceanspaces.com").with_env("S3_ACCESS_KEY", "${{ secrets.divvun-deploy.S3_ACCESS_KEY }}").with_env("S3_SECRET_KEY", "${{ secrets.divvun-deploy.S3_SECRET_KEY }}"))
        .find_or_create(f"cleanup.pahkat.uit.no.{CONFIG.index_path}")
    )

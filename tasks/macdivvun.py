from .common import macos_task, gha_pahkat, gha_setup, PAHKAT_REPO, NIGHTLY_CHANNEL
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript


def create_macdivvun_task():
    return (
        macos_task("MacDivvun")
        .with_gha("setup", gha_setup())
        .with_gha(
            "version",
            GithubAction(
                "divvun/taskcluster-gha/version",
                {
                    "xcode": ".",
                    "stable-channel": "beta",
                    "nightly-channel": NIGHTLY_CHANNEL,
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha("pahkat", gha_pahkat(["pahkat-uploader", "xcnotary"]))
        .with_gha(
            "build_macdivvun",
            GithubActionScript(
                """
            /bin/bash scripts/build.sh
        """
            )
            .with_env("VERSION", "${{ steps.version.outputs.version }}")
            .with_secret_input(
                "macos_developer_account", "divvun", "macos.developerAccount"
            )
            .with_secret_input(
                "macos_notarization_app_pwd", "divvun", "macos.appPassword"
            ),
        )
        .with_gha(
            "deploy",
            GithubAction(
                "divvun/taskcluster-gha/deploy",
                {
                    "platform": "macos",
                    "package-id": "macdivvun",
                    # TODO: Why was this commented out in the original CI? "repo": PAHKAT_REPO + "divvun-installer/",
                    "repo": PAHKAT_REPO + "tools/",
                    "macos-pkg-id": "no.divvun.MacDivvun",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "${GITHUB_WORKSPACE}/repo/MacDivvun.pkg",
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "github.token"),
        )
        .find_or_create(f"build.macdivvun.{CONFIG.index_path}")
    )

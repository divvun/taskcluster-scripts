from .common import macos_task, gha_pahkat, gha_setup, PAHKAT_REPO
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript


def create_divvun_manager_macos_task():
    return (
        macos_task("Divvun manager (macos)")
        .with_gha(
            "clone_pahkat",
            GithubAction(
                "actions/checkout",
                {
                    "repository": "divvun/pahkat",
                    "path": "${HOME}/tasks/${TASK_ID}/repo/pahkat",
                    "fetch-depth": 0,
                },
                enable_post=False,
            ).with_secret_input("token", "divvun", "github.token"),
        )
        .with_gha("setup", gha_setup())
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {
                    "xcode": ".",
                    "stable-channel": "beta",
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha(
            "self_update_channel",
            GithubActionScript(
                "echo ::set-output name=channel::nightly",
                run_if="${{ steps.version.outputs.channel == 'nightly' }}",
            ),
        )
        .with_gha(
            "install_rust",
            GithubAction(
                "actions-rs/toolchain",
                {
                    "toolchain": "stable",
                    "profile": "minimal",
                    "override": "true",
                    "components": "rustfmt",
                    "target": "x86_64-apple-darwin",
                },
            ),
        )
        .with_gha(
            "install_rust_aarch",
            GithubAction(
                "actions-rs/toolchain",
                {
                    "toolchain": "stable",
                    "profile": "minimal",
                    "override": "true",
                    "components": "rustfmt",
                    "target": "aarch64-apple-darwin",
                },
            ),
        )
        .with_gha("pahkat", gha_pahkat(["pahkat-uploader", "xcnotary"]))
        .with_gha(
            "build_service_x86",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": "--release --features launchd --bin server --manifest-path pahkat/pahkat-rpc/Cargo.toml --target x86_64-apple-darwin",
                },
            ).with_env("CHANNEL", "${{ steps.self_update_channel.outputs.channel }}"),
        )
        .with_gha(
            "build_service_aarch64",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": "--release --features launchd --bin server --manifest-path pahkat/pahkat-rpc/Cargo.toml --target aarch64-apple-darwin",
                },
            ).with_env("CHANNEL", "${{ steps.self_update_channel.outputs.channel }}"),
        )
        .with_gha(
            "lipo",
            GithubActionScript(
                """
            lipo -create pahkat/target/aarch64-apple-darwin/release/server pahkat/target/x86_64-apple-darwin/release/server -output "$GITHUB_WORKSPACE/repo/scripts/pahkatd"
        """
            ),
        )
        .with_gha(
            "build_divvun_manager",
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
                "Eijebong/divvun-actions/deploy",
                {
                    "platform": "macos",
                    "package-id": "divvun-installer",
                    "repo": PAHKAT_REPO + "divvun-installer/",
                    "macos-pkg-id": "no.divvun.Manager",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "${GITHUB_WORKSPACE}/repo/DivvunManager.pkg",
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "github.token"),
        )
        .find_or_create(f"build.divvun-manager-macos.{CONFIG.index_path}")
    )

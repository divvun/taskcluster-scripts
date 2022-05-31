from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import (
    linux_build_task,
    gha_setup,
    PAHKAT_REPO,
    NIGHTLY_CHANNEL,
)

def create_divvunspell_tasks():
    return (
        linux_build_task("Android divvunspell build")
            .with_apt_install("unzip")
            .with_gha("setup", gha_setup())
            .with_gha(
                "version",
                GithubAction(
                    "Eijebong/divvun-actions/version",
                    {
                        "cargo": "divvunspell/Cargo.toml",
                        "stable-channel": "beta",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
            )
            .with_gha("download_ndk", GithubActionScript("""
                cd $GITHUB_WORKSPACE
                curl -o android-ndk.zip https://dl.google.com/android/repository/android-ndk-r21e-linux-x86_64.zip
                unzip android-ndk.zip
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
            .with_gha("add_targets", GithubActionScript("""
                rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android i686-linux-android
            """))
            .with_gha("install_cargo_ndk", GithubActionScript("""
                cargo install cargo-ndk
            """))
            .with_gha("build", GithubAction("actions-rs/cargo", {
                "command": "ndk",
                "args": "-t armeabi-v7a -t arm64-v8a -o ./lib build -vv --lib --release --features internal_ffi",
            }).with_env("ANDROID_NDK_HOME", "$GITHUB_WORKSPACE/android-ndk-r21e"))
            .with_gha("prepare_lib", GithubActionScript("""
                mkdir -p lib/lib
                mv lib/arm* lib/lib
            """))
            .with_gha(
                "bundle_lib",
                GithubAction("Eijebong/divvun-actions/create-txz", {"path": "lib"}),
            )
            .with_gha(
                "deploy_lib",
                GithubAction(
                    "Eijebong/divvun-actions/deploy",
                    {
                        "package-id": "divvunspell",
                        "type": "TarballPackage",
                        "platform": "android",
                        "repo": PAHKAT_REPO + "devtools/",
                        "version": "${{ steps.version.outputs.version }}",
                        "channel": "${{ steps.version.outputs.channel }}",
                        "payload-path": "${{ steps.bundle_lib.outputs['txz-path'] }}",
                    },
                ),
            )
            .find_or_create(f"build.divvunspell.android.{CONFIG.index_path}")
    )


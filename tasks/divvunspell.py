from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript

from .common import (NIGHTLY_CHANNEL, PAHKAT_REPO, gha_pahkat, gha_setup,
                     linux_build_task, macos_task)


def create_divvunspell_tasks():
    create_android_build()
    create_macos_build()

def create_macos_build():
    return (
        macos_task("MacOS divvunspell build")
        .with_gha("setup", gha_setup())
        .with_gha("install_deps", gha_pahkat(["pahkat-uploader"]))
        .with_gha(
            "version",
            GithubAction(
                "divvun/taskcluster-gha/version",
                {
                    "cargo": "divvunspell/Cargo.toml",
                    "stable-channel": "beta",
                    "nightly-channel": NIGHTLY_CHANNEL,
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha(
            "install_rust",
            GithubAction(
                "actions-rs/toolchain",
                {
                    "toolchain": "stable",
                    "profile": "minimal",
                    "override": "true",
                    "target": "aarch64-apple-darwin",
                },
            ),
        )
        .with_gha(
            "build_rust",
            GithubAction(
                "actions-rs/cargo", {"command": "build", "args": "--release --lib --features compression,internal_ffi"}
            ),
        )
        .with_gha(
            "build_rust_aarch64",
            GithubAction(
                "actions-rs/cargo",
                {"command": "build", "args": "--release --target aarch64-apple-darwin --lib --features compression,internal_ffi"},
            ),
        )
        .with_gha("codesign aarch64", GithubAction("divvun/taskcluster-gha/codesign", {"path": "target/aarch64-apple-darwin/release/libdivvunspell.dylib" }))
        .with_gha("codesign x86_64", GithubAction("divvun/taskcluster-gha/codesign", {"path": "target/release/libdivvunspell.dylib" }))
        .with_gha("prepare_lib", GithubActionScript("""
            mkdir -p lib/lib/aarch64
            mkdir -p lib/lib/x86_64
            mv target/aarch64-apple-darwin/release/*.dylib lib/lib/aarch64
            mv target/release/*.dylib lib/lib/x86_64
        """))
        .with_gha(
            "bundle_lib",
            GithubAction("divvun/taskcluster-gha/create-txz", {"path": "lib"}),
        )
        .with_gha(
            "deploy_lib",
            GithubAction(
                "divvun/taskcluster-gha/deploy",
                {
                    "package-id": "libdivvunspell",
                    "type": "TarballPackage",
                    "platform": "macos",
                    "repo": PAHKAT_REPO + "devtools/",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "${{ steps.bundle_lib.outputs['txz-path'] }}",
                },
            ),
        )
        .find_or_create(f"build.divvunspell.macos.{CONFIG.index_path}")
    )



def create_android_build():
    return (
        linux_build_task("Android divvunspell build")
            .with_apt_install("unzip")
            .with_gha("setup", gha_setup())
            .with_gha("install_deps", gha_pahkat(["pahkat-uploader"]))
            .with_gha(
                "version",
                GithubAction(
                    "divvun/taskcluster-gha/version",
                    {
                        "cargo": "divvunspell/Cargo.toml",
                        "stable-channel": "beta",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
            )
            .with_gha("download_ndk", GithubActionScript("""
                cd $GITHUB_WORKSPACE
                curl -o android-ndk.zip https://dl.google.com/android/repository/android-ndk-r27c-linux.zip
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
            }).with_env("ANDROID_NDK_HOME", "$GITHUB_WORKSPACE/android-ndk-r27c"))
            .with_gha("prepare_lib", GithubActionScript("""
                mkdir -p lib/lib
                mv lib/arm* lib/lib
            """))
            .with_gha(
                "bundle_lib",
                GithubAction("divvun/taskcluster-gha/create-txz", {"path": "lib"}),
            )
            .with_gha(
                "deploy_lib",
                GithubAction(
                    "divvun/taskcluster-gha/deploy",
                    {
                        "package-id": "libdivvunspell",
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


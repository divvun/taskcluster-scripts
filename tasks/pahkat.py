from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import (
    windows_task,
    linux_build_task,
    gha_setup,
    gha_pahkat,
    PAHKAT_REPO,
    NIGHTLY_CHANNEL,
    generic_rust_build_upload_task,
    RUST_ENV,
)


def create_pahkat_tasks():
    create_pahkat_uploader_tasks()
    create_pahkat_windows_cli_task()
    create_pahkat_repomgr_tasks()
    create_pahkat_prefix_cli_tasks()
    create_pahkat_service_windows_task()
    create_pahkat_android_client_task()

def create_pahkat_android_client_task():
    return (
        linux_build_task("Android pahkat client build")
            .with_apt_install("unzip")
            .with_gha("setup", gha_setup())
            .with_gha("install_deps", gha_pahkat(["pahkat-uploader"]))
            .with_gha(
                "version",
                GithubAction(
                    "Eijebong/divvun-actions/version",
                    {
                        "cargo": "pahkat-client-core/Cargo.toml",
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
                "args": "-t armeabi-v7a -t arm64-v8a -o ./lib build -vv --features ffi,prefix --release",
            }).with_env("ANDROID_NDK_HOME", "$GITHUB_WORKSPACE/android-ndk-r21e").with_cwd("pahkat-client-core"))
            .with_gha("prepare_lib", GithubActionScript("""
                mkdir -p pahkat-client-core/lib/lib
                mv pahkat-client-core/lib/arm* pahkat-client-core/lib/lib
            """))
            .with_gha(
                "bundle_lib",
                GithubAction("Eijebong/divvun-actions/create-txz", {"path": "pahkat-client-core/lib"}),
            )
            .with_gha(
                "deploy_lib",
                GithubAction(
                    "Eijebong/divvun-actions/deploy",
                    {
                        "package-id": "libpahkat_client",
                        "type": "TarballPackage",
                        "platform": "android",
                        "repo": PAHKAT_REPO + "devtools/",
                        "version": "${{ steps.version.outputs.version }}",
                        "channel": "${{ steps.version.outputs.channel }}",
                        "payload-path": "${{ steps.bundle_lib.outputs['txz-path'] }}",
                    },
                ),
            )
            .find_or_create(f"build.pahkat.client_android.{CONFIG.index_path}")
    )


def create_pahkat_prefix_cli_tasks():
    def get_bootstrap_uploader(os_):
        """
        Enable this and change URLs when Brendan decides that pain is necessary...
        """
        BOOTSTRAP_VERSION = "0.2.0-nightly.20220203T084729034Z"
        if os_ == "macos":
            url = f"https://divvun.ams3.cdn.digitaloceanspaces.com/pahkat/artifacts/pahkat-uploader_{BOOTSTRAP_VERSION}_macos_x86_64.txz"
            temp = "${RUNNER_TEMP}"
        elif os_ == "windows":
            url = f"https://divvun.ams3.cdn.digitaloceanspaces.com/pahkat/artifacts/pahkat-uploader_{BOOTSTRAP_VERSION}_windows_i686.txz"
            temp = "$env:RUNNER_TEMP"
        elif os_ == "linux":
            url = f"https://divvun.ams3.cdn.digitaloceanspaces.com/pahkat/artifacts/pahkat-uploader_{BOOTSTRAP_VERSION}_linux_x86_64.txz"
            temp = "${RUNNER_TEMP}"
        else:
            raise NotImplementedError

        return GithubActionScript(
            f"""
            curl {url} -o uploader.txz
            xz -d uploader.txz
            tar xvf uploader.tar -C {temp}
            echo ::add-path::{temp}/bin
        """
        )

    # setup_uploader = get_bootstrap_uploader
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])
    get_features = lambda _: "--features prefix"

    return generic_rust_build_upload_task(
        "Pahkat prefix CLI",
        "pahkat-cli/Cargo.toml",
        package_id="pahkat-prefix-cli",
        target_dir="target",
        bin_name="pahkat-cli",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
        rename_binary="pahkat-prefix",
        get_features=get_features,
    )


def create_pahkat_uploader_tasks():
    # We're self boostrapping so add the dist directory in the path
    setup_uploader = lambda _: GithubActionScript("echo ::add-path::dist/bin")

    return generic_rust_build_upload_task(
        "Pahkat uploader",
        "pahkat-uploader/Cargo.toml",
        package_id="pahkat-uploader",
        target_dir="pahkat-uploader/target",
        bin_name="pahkat-uploader",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )


def create_pahkat_repomgr_tasks():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Pahkat repomgr",
        "pahkat-repomgr/Cargo.toml",
        package_id="pahkat-repomgr",
        target_dir="target",
        bin_name="repomgr",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )


def create_pahkat_service_windows_task():
    return (
        windows_task("Pahkat service (Windows)")
        .with_cmake()
        .with_gha("setup", gha_setup())
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {
                    "cargo": "pahkat-rpc/Cargo.toml",
                    "stable-channel": "beta",
                    "nightly-channel": NIGHTLY_CHANNEL,
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha("pahkat_setup", gha_pahkat(["pahkat-uploader"]))
        # The actions-rs action is broken on windows
        .with_gha(
            "install_rustup",
            GithubActionScript(
                "choco install -y --force rustup.install && echo ::add-path::${HOME}/.cargo/bin"
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
                    "target": "i686-pc-windows-msvc",
                },
            ),
        )
        .with_gha(
            "self_update_channel",
            GithubActionScript(
                f"Write-Host ::set-output name=channel::{NIGHTLY_CHANNEL}",
                run_if=f"${{{{ steps.version.outputs.channel == '{NIGHTLY_CHANNEL}' }}}}",
            ),
        )
        .with_gha(
            "rpc_lib",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": "-vv --lib --features windows --release --manifest-path pahkat-rpc/Cargo.toml --target i686-pc-windows-msvc",
                },
            )
            .with_env("RUSTC_BOOTSTRAP", 1)
            .with_env("CHANNEL", "${{ steps.self_update_channel.outputs.channel }}"),
        )
        .with_gha(
            "rpc_service",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": "-vv --bin winsvc --features windows --release --manifest-path pahkat-rpc/Cargo.toml --target i686-pc-windows-msvc",
                },
            )
            .with_env("RUSTC_BOOTSTRAP", 1)
            .with_env("CHANNEL", "${{ steps.self_update_channel.outputs.channel }}"),
        )
        .with_gha(
            "rpc_client",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": "-vv --bin client --features windows --release --manifest-path pahkat-rpc/Cargo.toml --target i686-pc-windows-msvc",
                },
            )
            .with_env("RUSTC_BOOTSTRAP", 1)
            .with_env("CHANNEL", "${{ steps.self_update_channel.outputs.channel }}"),
        )
        .with_gha(
            "create_dist",
            GithubActionScript(
                """
                mkdir dist
                move target\\i686-pc-windows-msvc\\release\\winsvc.exe dist\\pahkat-service.exe
                move target\\i686-pc-windows-msvc\\release\\client.exe dist\\pahkatc.exe
                mkdir dist-lib\\bin
                move target\\i686-pc-windows-msvc\\release\\pahkat_rpc.dll dist-lib\\bin\\pahkat_rpc.dll
            """
            ),
        )
        .with_gha(
            "sign_code_server",
            GithubAction(
                "Eijebong/divvun-actions/codesign", {"path": "dist/pahkat-service.exe"}
            ),
        )
        .with_gha(
            "sign_code_client",
            GithubAction(
                "Eijebong/divvun-actions/codesign", {"path": "dist/pahkatc.exe"}
            ),
        )
        .with_gha(
            "create_installer",
            GithubAction(
                "Eijebong/divvun-actions/inno-setup",
                {
                    "path": "pahkat-rpc/resources/install.iss",
                    "defines": "Version=${{ steps.version.outputs.version }}",
                },
            ),
        )
        .with_gha(
            "bundle_dll",
            GithubAction("Eijebong/divvun-actions/create-txz", {"path": "dist-lib"}),
        )
        .with_gha(
            "deploy_lib",
            GithubAction(
                "Eijebong/divvun-actions/deploy",
                {
                    "package-id": "libpahkat_rpc",
                    "type": "TarballPackage",
                    "platform": "windows",
                    "arch": "i686",
                    "repo": PAHKAT_REPO + "devtools/",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "${{ steps.bundle_dll.outputs['txz-path'] }}",
                },
            ),
        )
        .with_gha(
            "deploy_installer",
            GithubAction(
                "Eijebong/divvun-actions/deploy",
                {
                    "package-id": "pahkat-service",
                    "type": "TarballPackage",
                    "platform": "windows",
                    "arch": "i686",
                    "repo": PAHKAT_REPO + "divvun-installer/",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "${{ steps.create_installer.outputs['installer-path'] }}",
                    "windows-kind": "inno",
                    "windows-product-code": "{6B3A048B-BB81-4865-86CA-61A0DF038CFE}_is1",
                },
            ),
        )
        .find_or_create(f"build.pahkat.service_windows.{CONFIG.index_path}")
    )


def create_pahkat_windows_cli_task():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])
    get_features = lambda _: "--features windows"

    return generic_rust_build_upload_task(
        "Pahkat windows CLI",
        "pahkat-cli/Cargo.toml",
        package_id="pahkat-windows-cli",
        target_dir="target",
        bin_name="pahkat-cli",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
        rename_binary="pahkat-windows",
        get_features=get_features,
        only_os=["windows"],
    )

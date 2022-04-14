from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import (
    windows_task,
    gha_setup,
    gha_pahkat,
    PAHKAT_REPO,
    generic_rust_build_upload_task,
)

PAHKAT_RUST_ENV = {
    "RUST_VERSION": "stable",
    "CARGO_INCREMENTAL": "0",
    "RUSTUP_MAX_RETRIES": "10",
    "CARGO_NET_RETRY": "10",
    "RUST_BACKTRACE": "full",
    "LZMA_API_STATIC": "1",
}


def create_pahkat_tasks():
    create_pahkat_uploader_tasks()
    create_pahkat_windows_cli_task()
    create_pahkat_repomgr_tasks()
    create_pahkat_prefix_cli_tasks()
    create_pahkat_service_windows_task()


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
        env=PAHKAT_RUST_ENV,
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
        env=PAHKAT_RUST_ENV,
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
        env=PAHKAT_RUST_ENV,
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
                {"cargo": "pahkat-rpc/Cargo.toml", "stable-channel": "beta"},
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
                "Write-Host ::set-output name=channel::nightly",
                run_if="${{ steps.version.outputs.channel == 'nightly' }}",
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
        env=PAHKAT_RUST_ENV,
        setup_uploader=setup_uploader,
        rename_binary="pahkat-windows",
        get_features=get_features,
        only_os=["windows"],
    )

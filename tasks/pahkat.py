from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import (
    macos_task,
    windows_task,
    linux_build_task,
    gha_setup,
    gha_pahkat,
    PAHKAT_REPO,
)


def create_pahkat_tasks():
    create_pahkat_service_windows_task()
    # TODO: remove
    return
    for os_ in ("macos", "windows", "linux"):
        create_pahkat_uploader_task(os_)


def create_pahkat_uploader_task(os_):
    env = {
        "RUST_VERSION": "stable",
        "CARGO_INCREMENTAL": "0",
        "RUSTUP_MAX_RETRIES": "10",
        "CARGO_NET_RETRY": "10",
        "RUST_BACKTRACE": "full",
        "LZMA_API_STATIC": "1",
    }

    if os_ == "windows":
        task_new = windows_task
        install_rust = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt",
                "target": "i686-pc-windows-msvc",
            },
        )
        build = GithubAction(
            "actions-rs/cargo",
            {
                "command": "build",
                "args": "--release --manifest-path pahkat-uploader/Cargo.toml --target i686-pc-windows-msvc",
            },
        )
        dist = GithubActionScript(
            "mkdir dist\\bin && move pahkat-uploader\\target\\i686-pc-windows-msvc\\release\\pahkat-uploader.exe dist\\bin\\pahkat-uploader.exe"
        )
        sign = GithubAction(
            "Eijebong/divvun-actions/codesign", {"path": "dist/bin/pahkat-uploader.exe"}
        )
        deploy = GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": "pahkat-uploader",
                "type": "TarballPackage",
                "platform": "windows",
                "arch": "i686",
                "repo": PAHKAT_REPO + "devtools/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        )
    elif os_ == "macos":
        task_new = macos_task
        install_rust = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt",
            },
        )
        build = GithubAction(
            "actions-rs/cargo",
            {
                "command": "build",
                "args": "--release --manifest-path pahkat-uploader/Cargo.toml",
            },
        )
        dist = GithubActionScript(
            "mkdir -p dist/bin && mv pahkat-uploader/target/release/pahkat-uploader dist/bin/pahkat-uploader"
        )
        sign = GithubAction(
            "Eijebong/divvun-actions/codesign", {"path": "dist/bin/pahkat-uploader"}
        )
        deploy = GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": "pahkat-uploader",
                "type": "TarballPackage",
                "platform": "macos",
                "arch": "x86_64",
                "repo": PAHKAT_REPO + "devtools/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        )
    elif os_ == "linux":
        task_new = lambda name: linux_build_task(name).with_gha(
            "setup_linux", GithubActionScript("apt install -y musl musl-tools")
        )
        install_rust = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt",
                "target": "x86_64-unknown-linux-musl",
            },
        )
        build = GithubAction(
            "actions-rs/cargo",
            {
                "command": "build",
                "args": "--release --manifest-path pahkat-uploader/Cargo.toml",
            },
        )
        dist = GithubActionScript(
            "mkdir -p dist/bin && mv pahkat-uploader/target/release/pahkat-uploader dist/bin/pahkat-uploader"
        )
        sign = GithubActionScript('echo "No code signing on linux"')
        deploy = GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": "pahkat-uploader",
                "type": "TarballPackage",
                "platform": "linux",
                "arch": "x86_64",
                "repo": PAHKAT_REPO + "devtools/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        )
    else:
        raise NotImplementedError

    return (
        task_new(f"Pahkat uploader: {os_}")
        .with_env(**env)
        .with_script(
            r'call "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\Common7\Tools\VsDevCmd.bat"'
            if os_ == "windows"
            else ""
        )
        .with_gha("setup", gha_setup())
        # The actions-rs action is broken on windows
        .with_gha(
            "install_rustup",
            GithubActionScript(
                "choco install -y --force rustup.install && echo ::add-path::%HOMEDRIVE%%HOMEPATH%\\.cargo\\bin"
            ),
            enabled=(os_ == "windows"),
        )
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {"cargo": "pahkat-uploader/Cargo.toml", "nightly": "main, develop"},
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha("install_rust", install_rust)
        .with_gha("build", build)
        .with_gha("dist", dist)
        .with_gha("sign", sign)
        .with_gha(
            "tarball",
            GithubAction("Eijebong/divvun-actions/create-txz", {"path": "dist"}),
        )
        .with_gha(
            "add_uploader_to_path", GithubActionScript("echo ::add-path::dist/bin")
        )
        .with_gha(
            "deploy",
            deploy.with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_prep_gha_tasks()
        .find_or_create(f"build.pahkat.{os_}.{CONFIG.git_sha}")
    )


def create_pahkat_service_windows_task():
    return (
        windows_task("Pahkat service (Windows)")
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
                "choco install -y --force rustup.install && echo ::add-path::%HOMEDRIVE%%HOMEPATH%\\.cargo\\bin"
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
                "echo ::set-output name=channel::nightly",
                run_if="${{ steps.version.outputs.channel == 'nightly' }}",
            ),
        )
        .with_gha(
            "rpc_lib",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": "--lib --features windows --release --manifest-path pahkat-rpc/Cargo.toml --target i686-pc-windows-msvc",
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
                    "args": "--bin winsvc --features windows --release --manifest-path pahkat-rpc/Cargo.toml --target i686-pc-windows-msvc",
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
                    "args": "--bin client --features windows --release --manifest-path pahkat-rpc/Cargo.toml --target i686-pc-windows-msvc",
                },
            )
            .with_env("RUSTC_BOOTSTRAP", 1)
            .with_env("CHANNEL", "${{ steps.self_update_channel.outputs.channel }}"),
        )
        .with_gha(
            "create_dist",
            GithubActionScript("""
                mkdir dist
                move target\\i686-pc-windows-msvc\\release\\winsvc.exe dist\\pahkat-service.exe
                move target\\i686-pc-windows-msvc\\release\\client.exe dist\\pahkatc.exe
                mkdir dist-lib\\bin
                move target\\i686-pc-windows-msvc\\release\\pahkat_rpc.dll dist-lib\\bin\\pahkat_rpc.dll
            """),
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
        .with_prep_gha_tasks()
        .find_or_create(f"build.pahkat.service_windows.{CONFIG.git_sha}")
    )

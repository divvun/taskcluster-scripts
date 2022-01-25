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
    create_pahkat_prefix_cli_task()
    # TODO: remove
    return
    create_pahkat_service_windows_task()
    for os_ in ("macos", "windows", "linux"):
        create_pahkat_uploader_task()
        create_pahkat_repomgr_task(os_)


def create_pahkat_prefix_cli_task():
    env = {}

    def get_bootstrap_uploader(os_):
        """
        Enable this and change URLs when Brendan decides that pain is necessary...
        """
        if os_ == "macos":
            url = "https://divvun.ams3.cdn.digitaloceanspaces.com/pahkat/artifacts/pahkat-uploader_0.2.0-nightly.20220121T153431185Z_macos_x86_64.txz"
            temp = "${RUNNER_TEMP}"
        elif os_ == "windows":
            url = "https://divvun.ams3.cdn.digitaloceanspaces.com/pahkat/artifacts/pahkat-uploader_0.2.0-nightly.20220121T153431185Z_windows_i686.txz"
            temp = "%RUNNER_TEMP%"
        elif os_ == "linux":
            url = "https://divvun.ams3.cdn.digitaloceanspaces.com/pahkat/artifacts/pahkat-uploader_0.2.0-nightly.20220121T153431185Z_linux_x86_64.txz"
            temp = "${RUNNER_TEMP}"
        else:
            raise NotImplementedError

        return GithubActionScript(f"""
            curl {url} -o uploader.txz
            xz -d uploader.txz
            tar xvf uploader.tar -C {temp}
            echo ::add-path::{temp}/bin
        """)
    setup_uploader = get_bootstrap_uploader
    #setup_uploader = gha_pahkat(["pahkat-uploader"])

    get_features = lambda _: "--features prefix"

    return generic_rust_build_upload_task(
        "Pahkat prefix CLI",
        "pahkat-cli/Cargo.toml",
        package_id="pahkat-prefix-cli",
        target_dir="target",
        bin_name="pahkat-cli",
        env=env,
        setup_uploader=setup_uploader,
        rename_binary="pahkat-prefix",
        get_features=get_features
    )


def create_pahkat_uploader_task():
    env = {
        "RUST_VERSION": "stable",
        "CARGO_INCREMENTAL": "0",
        "RUSTUP_MAX_RETRIES": "10",
        "CARGO_NET_RETRY": "10",
        "RUST_BACKTRACE": "full",
        "LZMA_API_STATIC": "1",
    }

    # We're self boostrapping so add the dist directory in the path
    setup_uploader = lambda _: GithubActionScript("echo ::add-path::dist/bin")
    return generic_rust_build_upload_task(
        "Pahkat uploader",
        "pahkat-uploader/Cargo.toml",
        package_id="pahkat-uploader",
        target_dir="pahkat-uploader/target",
        bin_name="pahkat-uploader",
        env=env,
        setup_uploader=setup_uploader,
    )


def generic_rust_build_upload_task(
    task_name,
    cargo_toml_path,
    package_id,
    target_dir,
    bin_name,
    env,
    setup_uploader,
    rename_binary=None,
    get_features=None
):
    if rename_binary is None:
        rename_binary = bin_name
    for os_ in ("macos", "windows", "linux"):
        if get_features is not None:
            features = get_features(os_)
        else:
            features = ""
        _generic_rust_build_upload_task(
            os_,
            task_name,
            cargo_toml_path,
            package_id,
            target_dir,
            bin_name,
            env,
            setup_uploader(os_),
            rename_binary,
            features
        )


def _generic_rust_build_upload_task(
    os_,
    task_name,
    cargo_toml_path,
    package_id,
    target_dir,
    bin_name,
    env,
    setup_uploader,
    rename_binary,
    features,
):
    if os_ == "windows":
        target_dir = "\\".join(target_dir.split("/"))
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
                "args": f"--release {features} --manifest-path {cargo_toml_path} --target i686-pc-windows-msvc",
            },
        )
        dist = GithubActionScript(
            f"mkdir dist\\bin && move {target_dir}\\i686-pc-windows-msvc\\release\\{bin_name}.exe dist\\bin\\{rename_binary}.exe"
        )
        sign = GithubAction(
            "Eijebong/divvun-actions/codesign",
            {"path": f"dist/bin/{rename_binary}.exe"},
        )
        deploy = GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": package_id,
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
                "args": f"--release {features} --manifest-path {cargo_toml_path}",
            },
        )
        dist = GithubActionScript(
            f"mkdir -p dist/bin && mv {target_dir}/release/{bin_name} dist/bin/{rename_binary}"
        )
        sign = GithubAction(
            "Eijebong/divvun-actions/codesign", {"path": f"dist/bin/{rename_binary}"}
        )
        deploy = GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": package_id,
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
                "args": f"--release {features} --manifest-path {cargo_toml_path}",
            },
        )
        dist = GithubActionScript(
            f"mkdir -p dist/bin && mv {target_dir}/release/{bin_name} dist/bin/{rename_binary}"
        )
        sign = GithubActionScript('echo "No code signing on linux"')
        deploy = GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": package_id,
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
        task_new(f"{task_name}: {os_}")
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
                {"cargo": cargo_toml_path, "nightly": "main, develop"},
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
        .with_gha("setup_uploader", setup_uploader)
        .with_gha(
            "deploy",
            deploy.with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_prep_gha_tasks()
        .find_or_create(f"build.{bin_name}.{os_}.{CONFIG.git_sha}")
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
        .with_prep_gha_tasks()
        .find_or_create(f"build.pahkat.service_windows.{CONFIG.git_sha}")
    )


def create_pahkat_repomgr_task(os_):
    if os_ == "windows":
        task_new = windows_task
    elif os_ == "macos":
        task_new = macos_task
    elif os_ == "linux":
        task_new = lambda name: linux_build_task(name).with_gha(
            "setup_linux", GithubActionScript("apt install -y musl musl-tools")
        )
    else:
        raise NotImplementedError

    return (
        task_new("Pahkat repomgr")
        .with_gha("setup", gha_setup())
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {"cargo": "pahkat-repomgr/Cargo.toml"},
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
    )

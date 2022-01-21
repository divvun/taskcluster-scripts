from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import macos_task, windows_task, linux_build_task, gha_setup, gha_pahkat, PAHKAT_REPO

def create_pahkat_tasks():
    for os_ in ("macos", "windows", "linux"):
        create_pahkat_uploader_task(os_)


def create_pahkat_uploader_task(os_):
    env = {"RUST_VERSION": "stable", "CARGO_INCREMENTAL": "0", "RUSTUP_MAX_RETRIES": "10", "CARGO_NET_RETRY": "10", "RUST_BACKTRACE": "full",  "LZMA_API_STATIC": "1"}

    if os_ == "windows":
        task_new = windows_task
        install_rust = GithubAction("actions-rs/toolchain", {"toolchain": "stable", "profile": "minimal", "override": "true", "components": "rustfmt", "target": "i686-pc-windows-msvc"})
        build = GithubAction("actions-rs/cargo", {"command": "build", "args": "--release --manifest-path pahkat-uploader/Cargo.toml", "target": "i686-pc-windows-msvc"})
        dist = GithubActionScript("mkdir -p dist/bin && mv pahkat-uploader/target/i686-pc-windows-msvc/release/pahkat-uploader.exe dist/bin/pahkat-uploader.exe")
        sign = GithubAction("Eijebong/divvun-actions/codesign", {"path": "dist/bin/pahkat-uploader.exe"})
        deploy = GithubAction("Eijebong/divvun-actions/deploy", {"package-id": "pahkat-uploader", "type": "TarballPackage", "platform": "windows", "arch": "i686", "repo": PAHKAT_REPO})
    elif os_ == "macos":
        task_new = macos_task
        install_rust = GithubAction("actions-rs/toolchain", {"toolchain": "stable", "profile": "minimal", "override": "true", "components": "rustfmt"})
        build = GithubAction("actions-rs/cargo", {"command": "build", "args": "--release --manifest-path pahkat-uploader/Cargo.toml"})
        dist = GithubActionScript("mkdir -p dist/bin && mv pahkat-uploader/target/release/pahkat-uploader dist/bin/pahkat-uploader")
        sign = GithubAction("Eijebong/divvun-actions/codesign", {"path": "dist/bin/pahkat-uploader"})
        deploy = GithubAction("Eijebong/divvun-actions/deploy", {"package-id": "pahkat-uploader", "type": "TarballPackage", "platform": "macos", "arch": "x86_64", "repo": PAHKAT_REPO})
    elif os_ == "linux":
        task_new = lambda name: linux_build_task(name).with_gha("setup_linux", GithubActionScript("apt install -y musl musl-tools"))
        install_rust = GithubAction("actions-rs/toolchain", {"toolchain": "stable", "profile": "minimal", "override": "true", "components": "rustfmt", "target": "x86_64-unknown-linux-musl"})
        build = GithubAction("actions-rs/cargo", {"command": "build", "args": "--release --manifest-path pahkat-uploader/Cargo.toml"})
        dist = GithubActionScript("mkdir -p dist/bin && mv pahkat-uploader/target/release/pahkat-uploader dist/bin/pahkat-uploader")
        sign = GithubActionScript("echo \"No code signing on linux\"")
        deploy = GithubAction("Eijebong/divvun-actions/deploy", {"package-id": "pahkat-uploader", "type": "TarballPackage", "platform": "linux", "arch": "x86_64", "repo": PAHKAT_REPO})
    else:
        raise NotImplementedError

    return (task_new(f"Pahkat uploader: {os_}")
        .with_env(**env)
        .with_gha("setup", gha_setup())
        # The actions-rs action is broken on windows
        .with_gha("install_rustup", GithubActionScript("choco install -y --force rustup.install; refreshenv"), enabled=(os_=="windows"))
        .with_gha("version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {"cargo": "pahkat-uploader/Cargo.toml", "nightly": "main, develop"},
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN")
        )
        .with_gha("install_build_deps", gha_pahkat(["pahkat-uploader"]))
        .with_gha("install_rust", install_rust)
        .with_gha("build", build)
        .with_gha("dist", dist)
        .with_gha("sign", sign)
        .with_gha("tarball",
                GithubAction("Eijebong/divvun-actions/create-txz", {"path": "dist"}))
        .with_gha("deploy",
            deploy
            .with_mapped_output("version", "version", "version")
            .with_mapped_output("channel", "version", "channel")
            .with_mapped_output("payload-path", "tarball", "txz-path")
            .with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN")
        )
        .with_prep_gha_tasks()
        .find_or_create(f"build.pahkat.{os_}.{CONFIG.git_sha}")
    )


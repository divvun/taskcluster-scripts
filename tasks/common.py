import decisionlib
from typing import List, Optional, Dict, Any, Callable
from gha import GithubAction, GithubActionScript
from typing import List
from decisionlib import CONFIG
import os


BUILD_ARTIFACTS_EXPIRE_IN = "1 week"
PAHKAT_REPO = "https://pahkat.uit.no/"
NIGHTLY_CHANNEL = "nightly"
RUST_ENV = {
    "RUST_VERSION": "stable",
    "CARGO_INCREMENTAL": "0",
    "RUSTUP_MAX_RETRIES": "10",
    "CARGO_NET_RETRY": "10",
    "RUST_BACKTRACE": "full",
    "LZMA_API_STATIC": "1",
}


def linux_build_task(name, bundle_dest="repo", with_secrets=True, clone_self=True):
    task = (
        decisionlib.DockerWorkerTask(name)
        .with_worker_type("linux")
        .with_provisioner_id("divvun")
        .with_docker_image("ubuntu:22.04")
        # https://docs.taskcluster.net/docs/reference/workers/docker-worker/docs/caches
        .with_scopes("docker-worker:cache:divvun-*")
        .with_scopes("queue:get-artifact:private/*")
        .with_scopes("queue:get-artifact:public/*")
        .with_scopes("object:upload:divvun:*")
        .with_scopes("secrets:get:divvun" * with_secrets)
        .with_features("taskclusterProxy")
        .with_caches(
            **{
                "divvun-cargo-registry": "/root/.cargo/registry",
                "divvun-cargo-git": "/root/.cargo/git",
                "divvun-rustup": "/root/.rustup",
            }
        )
        .with_index_and_artifacts_expire_in(BUILD_ARTIFACTS_EXPIRE_IN)
        .with_max_run_time_minutes(60)
        .with_script("mkdir -p $HOME/tasks/$TASK_ID")
        .with_script("mkdir -p $HOME/tasks/$TASK_ID/_temp")
        .with_apt_update()
        .with_apt_install("curl", "git", "python3", "python3-pip", "lsb-release")
        .with_pip_install("taskcluster", "pyYAML", "awscli==1.31.6")
        .with_apt_install("wget", "nodejs")
        .with_apt_install("pkg-config", "libssl-dev")
        .with_additional_repo(
            os.environ["CI_REPO_URL"],
            "${HOME}/tasks/${TASK_ID}/ci",
            branch=os.environ["CI_REPO_REF"],
        )
        .with_gha(
            "clone",
            GithubAction(
                "actions/checkout",
                {
                    "repository": os.environ["REPO_FULL_NAME"],
                    "path": bundle_dest,
                    "ref": CONFIG.git_sha,
                    "fetch-depth": 0,
                },
                enable_post=False,
            ).with_secret_input("token", "divvun", "github.token"),
            enabled=clone_self and not CONFIG.index_read_only,
        )
        .with_additional_repo(
            os.environ["GIT_URL"],
            f"${{HOME}}/tasks/${{TASK_ID}}/{bundle_dest}",
            enabled=CONFIG.index_read_only,
        )
        .with_gha(
            "Set CWD",
            GithubActionScript(f"echo ::set-cwd::$HOME/tasks/$TASK_ID/{bundle_dest}"),
            enabled=clone_self,
        )
    )
    return task


def macos_task(name):
    return (
        decisionlib.MacOsGenericWorkerTask(name)
        .with_worker_type("macos")
        .with_scopes("queue:get-artifact:private/*")
        .with_scopes("queue:get-artifact:public/*")
        .with_scopes("object:upload:divvun:*")
        .with_scopes("secrets:get:divvun")
        .with_index_and_artifacts_expire_in(BUILD_ARTIFACTS_EXPIRE_IN)
        .with_max_run_time_minutes(60)
        .with_provisioner_id("divvun")
        .with_features("taskclusterProxy")
        .with_script("mkdir -p $HOME/tasks/$TASK_ID")
        .with_script("mkdir -p $HOME/tasks/$TASK_ID/_temp")
        .with_additional_repo(
            os.environ["CI_REPO_URL"],
            "${HOME}/tasks/${TASK_ID}/ci",
            branch=os.environ["CI_REPO_REF"],
        )
        .with_gha(
            "clone",
            GithubAction(
                "actions/checkout",
                {
                    "repository": os.environ["REPO_FULL_NAME"],
                    "path": "repo",
                    "fetch-depth": 0,
                },
                enable_post=False,
            ).with_secret_input("token", "divvun", "github.token"),
            enabled=not CONFIG.index_read_only,
        )
        .with_additional_repo(
            os.environ["GIT_URL"],
            "${HOME}/tasks/${TASK_ID}/repo",
            enabled=CONFIG.index_read_only,
        )
        .with_gha(
            "Set CWD", GithubActionScript(f"echo ::set-cwd::$HOME/tasks/$TASK_ID/repo")
        )
    )


def windows_task(name, clone_self=True):
    return (
        decisionlib.WindowsGenericWorkerTask(name)
        .with_worker_type("windows")
        .with_provisioner_id("divvun")
        .with_scopes("queue:get-artifact:private/*")
        .with_scopes("queue:get-artifact:public/*")
        .with_scopes("object:upload:divvun:*")
        .with_scopes("secrets:get:divvun")
        .with_index_and_artifacts_expire_in(BUILD_ARTIFACTS_EXPIRE_IN)
        .with_max_run_time_minutes(60)
        .with_script("mkdir %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%")
        .with_script("mkdir %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp")
        .with_features("taskclusterProxy")
        .with_git()
        .with_additional_repo(
            os.environ["CI_REPO_URL"],
            "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\ci",
            branch=os.environ["CI_REPO_REF"],
        )
        .with_gha(
            "clone",
            GithubAction(
                "actions/checkout",
                {
                    "repository": os.environ["REPO_FULL_NAME"],
                    "path": "repo",
                    "fetch-depth": 0,
                },
                enable_post=False,
            ).with_secret_input("token", "divvun", "github.token"),
            enabled=not CONFIG.index_read_only,
        )
        .with_additional_repo(
            os.environ["GIT_URL"],
            "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\repo",
            enabled=CONFIG.index_read_only,
        )
        .with_python3()
        .with_script("pip install --user taskcluster")
        .with_gha(
            "Set CWD",
            GithubActionScript(
                f"echo ::set-cwd::%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\repo"
            ),
            enabled=clone_self,
        )
        .with_gha(
            "Set CWD",
            GithubActionScript(f"echo ::set-cwd::%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%"),
            enabled=not clone_self,
        )
    )


def gha_setup():
    return GithubAction("divvun/taskcluster-gha/setup", {}).with_secret_input(
        "key", "divvun", "DIVVUN_KEY"
    )


def gha_pahkat(packages: List[str]):
    return GithubAction(
        "divvun/taskcluster-gha/pahkat/init",
        {
            "repo": "https://pahkat.uit.no/devtools/",
            "channel": NIGHTLY_CHANNEL,
            "packages": ",".join(packages),
        },
    )


def rust_task_for_os(os_):
    if os_ in ["windows", "windows_3264"]:
        install_rust = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt,clippy",
                "target": "i686-pc-windows-msvc",
            },
        )
        install_rust64 = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt,clippy",
                "target": "x86_64-pc-windows-msvc",
            },
        )
        return lambda name: (
            windows_task(name)
            .with_cmake()
            .with_rustup()
            .with_gha("install_rust", install_rust)
            .with_gha("install_rust64", install_rust64, enabled=(os_ == "windows_3264"))
        )
    elif os_ == "macos":
        install_rust = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt,clippy",
            },
        )
        return lambda name: macos_task(name).with_gha("install_rust", install_rust)
    elif os_ == "linux":
        install_rust = GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt,clippy",
                "target": "x86_64-unknown-linux-musl",
            },
        )
        return (
            lambda name: linux_build_task(name)
            .with_gha(
                "setup_linux", GithubActionScript("apt install -y musl musl-tools")
            )
            .with_gha("install_rust", install_rust)
        )
    else:
        raise NotImplementedError


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
    version_action,
    repository,
    depends_on,
):
    if os_ in ["windows", "windows_3264"]:
        target_dir = "\\".join(target_dir.split("/"))
        build = [
            (
                "build",
                GithubAction(
                    "actions-rs/cargo",
                    {
                        "command": "build",
                        "args": f"--release {features} --manifest-path {cargo_toml_path} --target i686-pc-windows-msvc --verbose",
                    },
                ),
            )
        ]
        dist = [
            (
                "dist",
                GithubActionScript(
                    f"mkdir dist\\bin && move {target_dir}\\i686-pc-windows-msvc\\release\\{bin_name}.exe dist\\bin\\{rename_binary}.exe"
                ),
            )
        ]
        sign = [
            (
                "sign",
                GithubAction(
                    "divvun/taskcluster-gha/codesign",
                    {"path": f"dist/bin/{rename_binary}.exe"},
                ),
            )
        ]

        if os_ == "windows_3264":
            build.append(
                (
                    "build32",
                    GithubAction(
                        "actions-rs/cargo",
                        {
                            "command": "build",
                            "args": f"--release {features} --manifest-path {cargo_toml_path} --target x86_64-pc-windows-msvc --verbose",
                        },
                    ),
                )
            )
            dist.append(
                (
                    "dist32",
                    GithubActionScript(
                        f"move {target_dir}\\x86_64-pc-windows-msvc\\release\\{bin_name}.exe dist\\bin\\{rename_binary}-x64.exe"
                    ),
                )
            )
            sign.append(
                (
                    "sign32",
                    GithubAction(
                        "divvun/taskcluster-gha/codesign",
                        {"path": f"dist/bin/{rename_binary}-x64.exe"},
                    ),
                )
            )

        deploy = GithubAction(
            "divvun/taskcluster-gha/deploy",
            {
                "package-id": package_id,
                "type": "TarballPackage",
                "platform": "windows",
                "arch": "i686" if os_ == "windows" else "",
                "repo": PAHKAT_REPO + repository + "/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        )
    elif os_ == "macos":
        build = [
            (
                "build",
                GithubAction(
                    "actions-rs/cargo",
                    {
                        "command": "build",
                        "args": f"--release {features} --manifest-path {cargo_toml_path}",
                    },
                ),
            )
        ]
        dist = [
            (
                "dist",
                GithubActionScript(
                    f"mkdir -p dist/bin && mv {target_dir}/release/{bin_name} dist/bin/{rename_binary}"
                ),
            )
        ]
        sign = [
            (
                "sign",
                GithubAction(
                    "divvun/taskcluster-gha/codesign",
                    {"path": f"dist/bin/{rename_binary}"},
                ),
            )
        ]
        deploy = GithubAction(
            "divvun/taskcluster-gha/deploy",
            {
                "package-id": package_id,
                "type": "TarballPackage",
                "platform": "macos",
                "arch": "x86_64",
                "repo": PAHKAT_REPO + repository + "/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        )
    elif os_ == "linux":
        build = [
            (
                "build",
                GithubAction(
                    "actions-rs/cargo",
                    {
                        "command": "build",
                        "args": f"--release {features} --manifest-path {cargo_toml_path}",
                    },
                ),
            )
        ]
        dist = [
            (
                "dist",
                GithubActionScript(
                    f"mkdir -p dist/bin && mv {target_dir}/release/{bin_name} dist/bin/{rename_binary}"
                ),
            )
        ]
        sign = [("sign", GithubActionScript('echo "No code signing on linux"'))]
        deploy = GithubAction(
            "divvun/taskcluster-gha/deploy",
            {
                "package-id": package_id,
                "type": "TarballPackage",
                "platform": "linux",
                "arch": "x86_64",
                "repo": PAHKAT_REPO + repository + "/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        )
    else:
        raise NotImplementedError

    return (
        rust_task_for_os(os_)(f"{task_name}: {os_}")
        .with_env(**env)
        .with_script(
            r'call "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\Common7\Tools\VsDevCmd.bat"'
            if os_ in ["windows", "windows_3264"]
            else ""
        )
        .with_gha("setup", gha_setup())
        # The actions-rs action is broken on windows
        .with_gha("version", version_action)
        .with_ghas(build)
        .with_ghas(dist)
        .with_ghas(sign)
        .with_gha(
            "tarball",
            GithubAction("divvun/taskcluster-gha/create-txz", {"path": "dist"}),
        )
        .with_gha("setup_uploader", setup_uploader)
        .with_gha(
            "deploy",
            deploy.with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_dependencies(*depends_on)
        .find_or_create(
            f"build.{package_id}__{bin_name}.deploy.{os_}.{CONFIG.index_path}"
        )
    )


def generic_rust_build_upload_task(
    task_name: str,
    cargo_toml_path: str,
    package_id: str,
    target_dir: str,
    bin_name: str,
    env: Dict[str, Any],
    setup_uploader: Callable[[str], GithubAction],
    rename_binary: Optional[str] = None,
    get_features: Optional[Callable[[str], str]] = None,
    version_action: Optional[GithubAction] = None,
    only_os: Optional[List[str]] = None,
    *,
    repository: str = "devtools",
    depends_on: List[str] = [],
):
    if rename_binary is None:
        rename_binary = bin_name
    if version_action is None:
        version_action = GithubAction(
            "divvun/taskcluster-gha/version",
            {"cargo": cargo_toml_path, "nightly-channel": NIGHTLY_CHANNEL},
        ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN")
    if only_os is None:
        only_os = ["macos", "windows", "linux"]

    for os_ in only_os:
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
            features,
            version_action,
            repository,
            depends_on,
        )


def generic_rust_task(index_name, name, setup_fn):
    oses = ["macos", "windows", "linux"]
    tasks = []
    for os_ in oses:
        task = rust_task_for_os(os_)("%s: %s" % (name, os_))
        setup_fn(task)
        task_id = task.find_or_create(f"build.{index_name}.{os_}.{CONFIG.index_path}")
        tasks.append(task_id)
    return tasks

def task_builder_for(os_):
    if os_ == "linux":
        return linux_build_task
    elif os_ == "windows":
        return windows_task
    elif os_ == "macos":
        return macos_task
    else:
        raise NotImplementedError()

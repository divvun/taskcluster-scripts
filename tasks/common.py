import decisionlib
from gha import GithubAction
from typing import List

BUILD_ARTIFACTS_EXPIRE_IN = "1 week"
PAHKAT_REPO = "https://pahkat.thetc.se/"


def linux_build_task(name, bundle_dest="repo", with_secrets=True):
    task = (
        decisionlib.DockerWorkerTask(name)
        .with_worker_type("linux")
        .with_provisioner_id("divvun")
        .with_docker_image("ubuntu:hirsute")
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
        .with_apt_install("curl", "git", "python3", "python3-pip")
        .with_pip_install("taskcluster", "pyYAML")
        .with_apt_install("wget", "nodejs")
        .with_repo_bundle("repo", bundle_dest)
        .with_repo_bundle("ci", "ci")
        .with_script(f"cd $HOME/tasks/$TASK_ID/{bundle_dest}")
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
        .with_repo_bundle("ci", "ci")
        .with_repo_bundle("repo", "repo")
        .with_script("cd $HOME/tasks/$TASK_ID/repo")
    )


def windows_task(name):
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
        .with_repo_bundle("ci", "ci")
        .with_repo_bundle("repo", "repo")
        .with_python3()
        .with_script("pip install --user taskcluster")
        .with_script("cd %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\repo")
    )

def gha_setup():
    return GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input(
        "key", "divvun", "DIVVUN_KEY"
    )

def gha_pahkat(packages: List[str]):
    return GithubAction(
        "Eijebong/divvun-actions/pahkat/init",
        {
            "repo": "https://pahkat.uit.no/devtools/",
            "channel": "nightly",
            "packages": ",".join(packages),
        },
    )

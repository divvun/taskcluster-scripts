from gha import GithubAction
from decisionlib import CONFIG
from .common import macos_task, windows_task, gha_setup, gha_pahkat, NIGHTLY_CHANNEL
import subprocess
import os


def create_kbd_tasks():
    print(subprocess.check_output("git init repo && cd repo && git fetch --depth 1 {} {} && git reset --hard FETCH_HEAD".format(CONFIG.git_url, CONFIG.git_ref), shell=True))
    has_windows_target = False
    has_macos_target = False

    for f in os.listdir('repo'):
        if f.endswith('.kbdgen'):
            bundle_path = os.path.join("repo", f)
            has_macos_target = os.path.isfile(os.path.join(bundle_path, "targets", "macos.yaml"))
            has_windows_target = os.path.isfile(os.path.join(bundle_path, "targets", "windows.yaml"))

    if has_macos_target:
        create_kbd_task("macos-latest")
    if has_windows_target:
        create_kbd_task("windows-latest")

def create_kbd_task(os_name):
    if os_name == "windows-latest":
        return (
            windows_task(f"Build keyboard: {os_name}")
            .with_git()
            .with_gha("setup", gha_setup())
            .with_gha("init", gha_pahkat(["pahkat-uploader", "kbdgen"]))
            .with_gha(
                "build",
                GithubAction(
                    "divvun/taskcluster-gha/keyboard/build",
                    {
                        "keyboard-type": "keyboard-windows",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ),
            )
            .with_gha(
                "codesign",
                GithubAction(
                    "divvun/taskcluster-gha/codesign",
                    { "path": "${{ steps.build.outputs['payload-path'] }}" },
                ),
            )
            .with_gha(
                "upload",
                GithubAction(
                    "divvun/taskcluster-gha/keyboard/deploy",
                    {
                        "keyboard-type": "keyboard-windows",
                        "payload-path": "${{ steps.codesign.outputs['signed-path'] }}",
                        "channel": "${{ steps.build.outputs.channel }}",
                    },
                    # TODO: remove branch when done developing
                    branch="windows-codesign",
                ),
            )
            .find_or_create(f"kbdgen.{os_name}_x64.{CONFIG.index_path}")
        )

    if os_name == "macos-latest":
        return (
            macos_task(f"Build keyboard: {os_name}")
            .with_gha("setup", gha_setup())
            .with_gha(
                "init",
                gha_pahkat(
                    [
                        "pahkat-uploader",
                        "kbdgen",
                        "xcnotary",
                    ]
                ),
            )
            .with_gha(
                "build",
                GithubAction(
                    "divvun/taskcluster-gha/keyboard/build",
                    {
                        "keyboard-type": "keyboard-macos",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ),
            )
            .with_gha(
                "upload",
                GithubAction(
                    "divvun/taskcluster-gha/keyboard/deploy",
                    {
                        "keyboard-type": "keyboard-macos",
                        "payload-path": "${{ steps.build.outputs['payload-path'] }}",
                        "channel": "${{ steps.build.outputs.channel }}",
                    },
                ),
            )
            .find_or_create(f"kbdgen.{os_name}_x64.{CONFIG.index_path}")
        )

    raise NotImplementedError

from gha import GithubAction
from decisionlib import CONFIG
from .common import macos_task, windows_task


def create_kbd_task(os_name):
    if os_name == "windows-latest":
        return (
            windows_task(f"Build keyboard: {os_name}")
            .with_git()
            .with_gha(
                "setup",
                GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input(
                    "key", "divvun", "DIVVUN_KEY"
                ),
            )
            .with_gha(
                "init",
                GithubAction(
                    "Eijebong/divvun-actions/pahkat/init",
                    {
                        "repo": "https://pahkat.uit.no/devtools/",
                        "channel": "nightly",
                        "packages": "pahkat-uploader, kbdgen",
                    },
                ),
            )
            .with_gha(
                "build",
                GithubAction(
                    "Eijebong/divvun-actions/keyboard/build",
                    {"keyboard-type": "keyboard-windows"},
                ),
            )
            .with_gha(
                "upload",
                GithubAction(
                    "Eijebong/divvun-actions/keyboard/deploy",
                    {"keyboard-type": "keyboard-windows"},
                ).with_mapped_output(
                    "payload-path", "build", "payload-path"
                ).with_mapped_output(
                    "channel", "build", "channel"
                ),
            )
            .with_prep_gha_tasks()
            .find_or_create(f"kbdgen.{os_name}_x64.{CONFIG.git_sha}")
        )

    if os_name == "macos-latest":
        return (
            macos_task(f"Build keyboard: {os_name}")
            .with_gha(
                "setup",
                GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input(
                    "key", "divvun", "DIVVUN_KEY"
                ),
            )
            .with_gha(
                "init",
                GithubAction(
                    "Eijebong/divvun-actions/pahkat/init",
                    {
                        "repo": "https://pahkat.uit.no/devtools/",
                        "channel": "nightly",
                        "packages": "pahkat-uploader, kbdgen@2.0.0-nightly.20210622T210632Z, xcnotary",
                    },
                ),
            )
            .with_gha(
                "build",
                GithubAction(
                    "Eijebong/divvun-actions/keyboard/build",
                    {"keyboard-type": "keyboard-macos"},
                ),
            )
            .with_prep_gha_tasks()
            .find_or_create(f"kbdgen.{os_name}_x64.{CONFIG.git_sha}")
        )

    raise NotImplementedError

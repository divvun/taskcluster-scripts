from gha import GithubAction
from decisionlib import CONFIG
from .common import macos_task, windows_task, gha_setup, gha_pahkat, NIGHTLY_CHANNEL


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
                    "Eijebong/divvun-actions/keyboard/build",
                    {
                        "keyboard-type": "keyboard-windows",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ),
            )
            .with_gha(
                "upload",
                GithubAction(
                    "Eijebong/divvun-actions/keyboard/deploy",
                    {
                        "keyboard-type": "keyboard-windows",
                        "payload-path": "${{ steps.build.outputs['payload-path'] }}",
                        "channel": "${{ steps.build.outputs.channel }}",
                    },
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
                    "Eijebong/divvun-actions/keyboard/build",
                    {
                        "keyboard-type": "keyboard-macos",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ),
            )
            .with_gha(
                "upload",
                GithubAction(
                    "Eijebong/divvun-actions/keyboard/deploy",
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

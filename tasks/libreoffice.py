from .common import linux_build_task, windows_task, gha_setup, gha_pahkat, PAHKAT_REPO, NIGHTLY_CHANNEL
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript


def create_libreoffice_tasks():
    oxt_task = (
        linux_build_task("Build OXT")
        .with_gha(
            "Download artifacts",
            GithubAction(
                "dawidd6/action-download-artifact@v2",
                {
                    "workflow": "ci.yml",
                    "branch": "main",
                    "name": "lib-windows-x86_64",
                    "repo": "divvun/divvunspell",
                },
            ).with_secret_input("github_token", "divvun", "github.token"),
        )
        .with_gha("setup_pahkat", gha_pahkat(["pahkat-uploader"]))
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {
                    "filepath": "VERSION",
                    "nightly-channel": NIGHTLY_CHANNEL
                },
            ),
        )
        .with_apt_install("zip")
        .with_gha(
            "Create OXT",
            GithubActionScript(
                """
        mkdir -p lib/win32-amd64
        mv *.dll lib/win32-amd64
        zip -r divvunspell.zip *
        mv divvunspell.zip /divvunspell.oxt
        cd /
        tar caf divvunspell.oxt.txz divvunspell.oxt
        """
            ),
        )
        .with_gha(
            "deploy",
            GithubAction(
                "Eijebong/divvun-actions/deploy",
                {
                    "package-id": "divvunspell-libreoffice-oxt",
                    "type": "TarballPackage",
                    "platform": "windows",
                    "repo": PAHKAT_REPO + "devtools/",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "/divvunspell.oxt.txz",
                },
            ),
        )
        .with_artifacts("/divvunspell.oxt")
        .find_or_create(f"build.libreoffice.linux_x64.{CONFIG.index_path}")
    )

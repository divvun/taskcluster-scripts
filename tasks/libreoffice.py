from .common import (
    macos_task,
    gha_pahkat,
    PAHKAT_REPO,
    NIGHTLY_CHANNEL,
)
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript


def create_libreoffice_tasks():
    return (
        macos_task("Build OXT")
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
                {"filepath": "VERSION", "nightly-channel": NIGHTLY_CHANNEL},
            ),
        )
        .with_gha(
            "Create OXT",
            GithubActionScript(
                """
        mkdir -p lib/win32-amd64
        mv *.dll lib/win32-amd64
        zip -r divvunspell.zip *
        rm -Rf lib
        mv divvunspell.zip $HOME
        cd $HOME
        tar caf divvunspell.oxt.txz divvunspell.oxt
        """
            ),
        )
        .with_gha("Prepare macos OXT", GithubActionScript("""
        mkdir -p lib/darwin-x86_64
        mkdir -p lib/darwin-arm64
        """))
        .with_gha(
            "Download artifacts macos",
            GithubAction(
                "dawidd6/action-download-artifact@v2",
                {
                    "workflow": "ci.yml",
                    "branch": "main",
                    "name": "lib-darwin-aarch64",
                    "repo": "divvun/divvunspell",
                    "path": "lib/darwin-arm64",
                },
            ).with_secret_input("github_token", "divvun", "github.token"),
        )
        .with_gha(
            "Download artifacts macos (x64)",
            GithubAction(
                "dawidd6/action-download-artifact@v2",
                {
                    "workflow": "ci.yml",
                    "branch": "main",
                    "name": "lib-darwin-x86_64",
                    "repo": "divvun/divvunspell",
                    "path": "lib/darwin-x86_64",
                },
            ).with_secret_input("github_token", "divvun", "github.token"),
        )
        .with_gha(
            "Create macos OXT",
            GithubActionScript(
                """
        zip -r divvunspell.zip *
        rm -Rf lib
        mv divvunspell.zip $HOME/divvunspell-macos.oxt
        cd $HOME
        tar caf divvunspell-macos.oxt.txz divvunspell-macos.oxt
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
                    "payload-path": "/$HOME/divvunspell.oxt.txz",
                },
            ),
        )
        .with_artifacts("/$HOME/divvunspell.oxt")
        .with_artifacts("/$HOME/divvunspell-macos.oxt")
        .find_or_create(f"build.libreoffice.linux_x64.{CONFIG.index_path}")
    )

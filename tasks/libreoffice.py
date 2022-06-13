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
        .with_gha("setup_pahkat", gha_pahkat(["pahkat-uploader", "xcnotary"]))
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {"filepath": "src/VERSION", "nightly-channel": NIGHTLY_CHANNEL},
            ),
        )
        .with_gha(
            "Create OXT",
            GithubActionScript(
                """
        mkdir -p src/lib/win32-amd64
        mv *.dll src/lib/win32-amd64
        cd src
        zip -r divvunspell.zip *
        cd ..
        rm -Rf src/lib
        mv src/divvunspell.zip $TC_TASK_DIR/divvunspell.oxt
        cd $TC_TASK_DIR
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
                    "payload-path": "$TC_TASK_DIR/divvunspell.oxt.txz",
                },
            ),
        )
        .with_gha(
            "get_divvunspell_nightly_macos",
            GithubActionScript(
                f"""
                curl -Ls "https://pahkat.uit.no/devtools/download/libdivvunspell?platform=macos&channel={NIGHTLY_CHANNEL}" -o libdivvunspell.txz
                xz -d libdivvunspell.txz
                tar xvf divvunspell-libreoffice-oxt.tar
                mkdir -p src/lib/darwin-x86_64
                mkdir -p src/lib/darwin-arm64
                mv lib/x86_64/* src/lib/darwin-x86_64
                mv lib/aarch64/* src/lib/darwin-arm64
                rm -Rf lib
            """
            ),
        )
        .with_gha(
            "Create macos OXT",
            GithubActionScript(
                """
        cd src
        zip -r divvunspell.zip *
        cd ..
        rm -Rf src/lib
        mv src/divvunspell.zip $TC_TASK_DIR/divvunspell-macos.oxt
        cd $TC_TASK_DIR
        tar caf divvunspell-macos.oxt.txz divvunspell-macos.oxt
        """
            ),
        )
        .with_gha(
            "deploy_macos",
            GithubAction(
                "Eijebong/divvun-actions/deploy",
                {
                    "package-id": "divvunspell-libreoffice-oxt",
                    "type": "TarballPackage",
                    "platform": "macos",
                    "repo": PAHKAT_REPO + "devtools/",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "$TC_TASK_DIR/divvunspell-macos.oxt.txz",
                },
            ),
        )
        .with_gha("Create macos installer",
            GithubActionScript(
            """
                cp $TC_TASK_DIR/divvunspell-macos.oxt macos/divvunspell.oxt
                cd macos
                ./build.sh
            """)
        )
        .with_gha("codesign macos installer", GithubAction("Eijebong/divvun-actions/codesign", {"path": "macos/LibreOfficeOXT.pkg" }))
        .with_gha(
            "deploy_macos_installer",
            GithubAction(
                "Eijebong/divvun-actions/deploy",
                {
                    "package-id": "divvunspell-libreoffice",
                    "type": "MacOSPackage",
                    "platform": "macos",
                    "macos-pkg-id": "no.divvun.LibreOfficeOXT",
                    "repo": PAHKAT_REPO + "tools/",
                    "version": "${{ steps.version.outputs.version }}",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "payload-path": "macos/LibreOfficeOXT.pkg",
                },
            ),
        )
        .with_artifacts("divvunspell.oxt")
        .with_artifacts("divvunspell-macos.oxt")
        .find_or_create(f"build.libreoffice.linux_x64.{CONFIG.index_path}")
    )

from decisionlib import CONFIG
from .common import windows_task, gha_setup, gha_pahkat, PAHKAT_REPO
from gha import GithubAction, GithubActionScript


def create_spelli_task():
    return (
        windows_task("Spelli build")
        .with_gha("setup", gha_setup())
        .with_rustup()
        .with_gha(
            "rustup_setup",
            GithubAction(
                "actions-rs/toolchain",
                {
                    "profile": "minimal",
                    "toolchain": "nightly",
                    "override": "true",
                    "default": "true",
                    "components": "rust-src",
                    "target": "i686-pc-windows-msvc",
                },
            ),
        )
        .with_gha(
            "version",
            GithubAction(
                "Eijebong/divvun-actions/version",
                {"cargo": "true"},
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha(
            "pahkat",
            gha_pahkat(
                ["pahkat-uploader"]
            ),
        )
        .with_gha(
            "get_oxt_nightly",
            GithubActionScript(
                """
                curl -Ls "https://pahkat.uit.no/devtools/download/divvunspell-libreoffice-oxt?platform=windows&channel=nightly" -o divvunspell-libreoffice-oxt.txz
                xz -d divvunspell-libreoffice-oxt.txz
                tar xvf divvunspell-libreoffice-oxt.tar
                mv divvunspell.oxt divvunspell-libreoffice.oxt
        """,
                run_if="${{ steps.version.outputs.channel == 'nightly' }}",
            ),
        )
        .with_gha(
            "get_pahkat_service_stable",
            GithubActionScript(
                """
                curl -Ls "https://pahkat.uit.no/devtools/download/divvunspell-libreoffice-oxt?platform=windows&channel=beta" -o divvunspell-libreoffice-oxt.txz
                xz -d divvunspell-libreoffice-oxt.txz
                tar xvf divvunspell-libreoffice-oxt.tar
                mv divvunspell.oxt divvunspell-libreoffice.oxt
        """,
                run_if="${{ steps.version.outputs.channel != 'nightly' }}",
            ),
        )
        .with_gha("build", GithubAction(
            "actions-rs/cargo",
            {
                "command": "build",
                "args": f"--release --target i686-pc-windows-msvc",
            },
        ))
        .with_gha("create_dist", GithubActionScript(
            f"mkdir dist\\bin && move target\\i686-pc-windows-msvc\\release\\spelli.exe dist\\bin\\spelli.exe"
        ))
        .with_gha(
            "sign_spelli",
            GithubAction(
                "Eijebong/divvun-actions/codesign",
                {
                    "path": "dist/bin/spelli.exe"
                },
            ),
        )
        .with_gha(
            "tarball",
            GithubAction("Eijebong/divvun-actions/create-txz", {"path": "dist"}),
        )
        .with_gha("deploy", GithubAction(
            "Eijebong/divvun-actions/deploy",
            {
                "package-id": "spelli",
                "type": "TarballPackage",
                "platform": "windows",
                "arch": "i686",
                "repo": PAHKAT_REPO + "devtools/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "${{ steps.tarball.outputs['txz-path'] }}",
            },
        ))
        .find_or_create(f"build.spelli.{CONFIG.index_path}")
    )


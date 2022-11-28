from decisionlib import CONFIG
from .common import windows_task, gha_setup, gha_pahkat, PAHKAT_REPO, NIGHTLY_CHANNEL
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
                "divvun/taskcluster-gha/version",
                {"cargo": "true", "nightly-channel": NIGHTLY_CHANNEL},
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha(
            "pahkat",
            gha_pahkat(["pahkat-uploader"]),
        )
        .with_gha(
            "get_oxt_nightly",
            GithubActionScript(
                f"""
                curl -Ls "https://pahkat.uit.no/devtools/download/divvunspell-libreoffice-oxt?platform=windows&channel={NIGHTLY_CHANNEL}" -o divvunspell-libreoffice-oxt.txz
                xz -d divvunspell-libreoffice-oxt.txz
                tar xvf divvunspell-libreoffice-oxt.tar
                mv divvunspell.oxt divvunspell-libreoffice.oxt
        """,
                run_if=f"${{{{ steps.version.outputs.channel == '{NIGHTLY_CHANNEL}' }}}}",
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
                run_if=f"${{{{ steps.version.outputs.channel != '{NIGHTLY_CHANNEL}' }}}}",
            ),
        )
        .with_gha(
            "build",
            GithubAction(
                "actions-rs/cargo",
                {
                    "command": "build",
                    "args": f"--release --target i686-pc-windows-msvc",
                },
            ),
        )
        .with_gha(
            "create_dist",
            GithubActionScript(
                f"mkdir dist\\bin && move target\\i686-pc-windows-msvc\\release\\spelli.exe dist\\bin\\spelli.exe"
            ),
        )
        .with_gha(
            "sign_spelli",
            GithubAction(
                "divvun/taskcluster-gha/codesign",
                {"path": "dist/bin/spelli.exe"},
            ),
        )
        .with_gha(
            "tarball",
            GithubAction("divvun/taskcluster-gha/create-txz", {"path": "dist"}),
        )
        .with_gha(
            "deploy",
            GithubAction(
                "divvun/taskcluster-gha/deploy",
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
            ),
        )
        .find_or_create(f"build.spelli.{CONFIG.index_path}")
    )

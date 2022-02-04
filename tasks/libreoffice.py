from .common import linux_build_task, windows_task, gha_setup, gha_pahkat, PAHKAT_REPO
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript

def create_libreoffice_tasks():
    oxt_task = (linux_build_task("Build OXT")
        .with_gha("Download artifacts", GithubAction("dawidd6/action-download-artifact@v2", {
            "workflow": "ci.yml",
            "branch": "main",
            "name": "lib-windows-x86_64",
            "repo": "divvun/divvunspell",
        }).with_secret_input("github_token", "divvun", "github.token"))
        .with_apt_install("zip")
        .with_gha("Create OXT", GithubActionScript("""
        mkdir -p lib/win32-amd64
        mv *.dll lib/win32-amd64
        zip -r divvunspell.zip *
        mv divvunspell.zip /divvunspell.oxt
        """))
        .with_artifacts("/divvunspell.oxt")
        .find_or_create(f"build.libreoffice.linux_x64.{CONFIG.git_sha}")
    )

    (windows_task("Create installer")
        .with_curl_artifact_script(oxt_task, "divvunspell.oxt", out_directory="%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%")
        .with_gha("Clone minst", GithubAction("actions/checkout@v2", {
            "repository": "divvun/minst",
            "path": "repo/minst",
        }).with_secret_input("token", "divvun", "github.token"))
        .with_rustup()
        .with_gha("setup", gha_setup())
        .with_gha("install_uploader", gha_pahkat(["pahkat-uploader"]))
        .with_gha("Install rust", GithubAction(
            "actions-rs/toolchain",
            {
                "toolchain": "stable",
                "profile": "minimal",
                "override": "true",
                "components": "rustfmt",
            },
        ))
        .with_gha("Move oxt in the right place", GithubActionScript("""
            mv $env:HOME\\$env:TASK_ID\\divvunspell.oxt minst/divvunspell-libreoffice.oxt
        """))
        .with_gha("Build uninstaller", GithubAction("actions-rs/cargo", {
            "command": "build",
            "args": f"--release --example oxtuninst --manifest-path minst/Cargo.toml"
        }))
        .with_gha("Sign uninstaller", GithubAction(
            "Eijebong/divvun-actions/codesign",
            {"path": f"minst/target/release/examples/oxtuninst.exe"},
        ))
        .with_gha("Build installer", GithubAction("actions-rs/cargo", {
            "command": "build",
            "args": f"--release --example oxtinst --manifest-path minst/Cargo.toml"
        }))
        .with_gha("Sign installer", GithubAction(
            "Eijebong/divvun-actions/codesign",
            {"path": f"minst/target/release/examples/oxtinst.exe"},
        ))
        .with_gha("version", GithubAction("Eijebong/divvun-actions/version", {
            "filepath": "VERSION",
        }))
        .with_gha("deploy", GithubAction("Eijebong/divvun-actions/deploy",
            {
                "package-id": "divvunspell-libreoffice",
                "type": "WindowsExecutable",
                "platform": "windows",
                "repo": PAHKAT_REPO + "tools/",
                "version": "${{ steps.version.outputs.version }}",
                "channel": "${{ steps.version.outputs.channel }}",
                "payload-path": "minst\\target\\release\\examples\\oxtinst.exe",
                "windows-product-code": "{068F854F-0A4E-5C59-8A89-9B1263A85C46}_is1",
            },
        ))
        .find_or_create(f"build.libreoffice.windows.{CONFIG.git_sha}")
    )
from .common import windows_task, gha_setup, gha_pahkat
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript

def create_windivvun_tasks():
    windivvun_tasks = create_windivvun_build_tasks()
    mso_tasks = create_mso_build_tasks()
    task = windows_task("Windivvun installer").with_script("mkdir artifacts", as_gha=True)
    for (task_id, artifact) in windivvun_tasks:
        task.with_curl_artifact_script(task_id, artifact, out_directory="artifacts", as_gha=True)
    for (task_id, artifact) in mso_tasks:
        task.with_curl_artifact_script(task_id, artifact, out_directory="artifacts", as_gha=True)

    return (task
        .with_gha("setup", gha_setup())
        .with_gha("version", GithubAction("Eijebong/divvun-actions/version", {
            "cargo": "true",
        }).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"))
        .with_gha("pahkat", gha_pahkat(["pahkat-uploader", "spelli"]))
        .with_gha("move_artifacts", GithubActionScript("""
            cp $env:RUNNER_WORKSPACE\\pahkat-prefix\\pkg\\spelli\\bin\\spelli.exe artifacts\\
        """))
        .with_gha("build_installer", GithubAction("Eijebong/divvun-actions/inno-setup", {
            "path": "install.iss",
            "defines": "Version=${{ steps.version.outputs.version }}",
        }))
        .with_gha("deploy", GithubAction("Eijebong/divvun-actions/deploy", {
            "package-id": "windivvun",
            "platform": "windows",
            "payload-path": "${{ steps.installer.outputs['installer-path'] }}",
            "version": "${{ steps.version.outputs.version }}",
            "repo": "https://pahkat.uit.no/tools",
            "channel": "${{ steps.version.outputs.channel }}",
            "windows-kind": "inno",
            "windows-product-code": "{41F71B6E-DE82-433D-8659-7E2D7C3B95E2}_is1",
        }).with_secret_input("GITHUB_TOKEN", "divvun", "github.token"))
        .find_or_create(f"build.windivvun-installer.{CONFIG.git_sha}")
    )

def create_mso_build_tasks():
    matrix = [("i686-pc-windows-msvc", "vcvars32.bat", "i686"), ("x86_64-pc-windows-msvc", "vcvars64.bat", "x86_64")]
    mso_tasks = []
    for (triple, vcvars, arch) in matrix:
        mso_tasks.append((
            windows_task("MSO build: %s" % arch, clone_self=False)
            .with_rustup()
            .with_gha("clone_mso", GithubAction("actions/checkout", {
                "repository": "mso-nda-resources",
            }).with_secret_input("token", "divvun", "github.token"))
            .with_gha("setup", gha_setup())
            .with_gha("rustup", GithubAction("actions-rs/toolchain", {
                "toolchain": "stable-" + triple,
                "profile": "minimal",
                "override": "true",
            }))
            .with_gha("build", GithubActionScript(f"""
              cd divvunspell-mso
              "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\BuildTools\\VC\\Auxiliary\\Build\\{vcvars}"
              cargo build --target {triple} --release
            """).with_secret_input("SENTRY_DSN", "divvun", "MSO_DSN"))
            .with_gha(
                "sign",
                GithubAction(
                    "Eijebong/divvun-actions/codesign",
                    {
                        "path": f"target/{triple}/release/divvunspellmso.dll"
                    },
                ),
            )
            .with_artifacts(f"target/{triple}/release/divvunspellmso.dll")
            .find_or_create(f"build.windivvun-mso.{arch}.{CONFIG.git_sha})"),
            f"target/{triple}/release/divvunspellmso.dll"
        ))

    return mso_tasks

def create_windivvun_build_tasks():
    matrix = [("i686-pc-windows-msvc", "vcvars32.bat", "i686"), ("x86_64-pc-windows-msvc", "vcvars64.bat", "x86_64")]
    windivvun_tasks = []
    for (triple, vcvars, arch) in matrix:
        windivvun_tasks.append((
            windows_task("Build windivvun: %s" % arch)
            .with_rustup()
            .with_gha("setup", gha_setup())
            .with_gha("rustup", GithubAction("actions-rs/toolchain", {
                "toolchain": "stable-" + triple,
                "profile": "minimal",
                "override": "true",
            }))
            .with_gha("build", GithubActionScript(f"""
              "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\BuildTools\\VC\\Auxiliary\\Build\\{vcvars}"
              cargo build --target {triple} --release
            """))
            .with_gha(
                "sign",
                GithubAction(
                    "Eijebong/divvun-actions/codesign",
                    {
                        "path": f"target/{triple}/release/windivvun.dll"
                    },
                ),
            )
            .with_artifacts(f"repo/target/{triple}/release/windivvun.dll")
            .find_or_create(f"build.windivvun.{arch}.{CONFIG.git_sha})"),
            f"target/{triple}/release/windivvun.dll"
        ))

    return windivvun_tasks



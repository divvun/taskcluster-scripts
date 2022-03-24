from .common import windows_task, gha_setup, gha_pahkat
from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript

def create_windivvun_tasks():
    windivvun_tasks = create_windivvun_build_tasks()
    mso_tasks = create_mso_build_tasks()
    task = windows_task("Windivvun installer").with_script("mkdir artifacts", as_gha=True)
    for (task_id, arch) in windivvun_tasks:
        (task
            .with_script(f"mkdir artifacts/windivvun-{arch}", as_gha=True)
            .with_curl_artifact_script(task_id, "windivvun.dll", out_directory=f"artifacts/windivvun-{arch}", as_gha=True)
        )
    for (task_id, arch) in mso_tasks:
        (task
            .with_script(f"mkdir artifacts/divvunspell-mso-{arch}", as_gha=True)
            .with_curl_artifact_script(task_id, "divvunspellmso.dll", out_directory=f"artifacts/divvunspell-mso-{arch}", as_gha=True)
        )

    return (task
        .with_gha("setup", gha_setup())
        .with_gha("version", GithubAction("Eijebong/divvun-actions/version", {
            "cargo": "true",
        }).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"))
        .with_gha("pahkat", gha_pahkat(["pahkat-uploader"]))
        .with_gha("download_spelli_stable", GithubActionScript("""
            curl -Ls "https://pahkat.uit.no/devtools/download/spelli?platform=windows&channel=beta" -o artifacts\\spelli.exe.txz
            cd artifacts
            xz -d spelli.exe.txz
            tar xvf spelli.exe.tar
            mv bin/spelli.exe .
        """, run_if="${{ steps.version.outputs.channel != 'nightly' }}"))
        .with_gha("download_spelli_nightly", GithubActionScript("""
            curl -Ls "https://pahkat.uit.no/devtools/download/spelli?platform=windows&channel=nightly" -o artifacts\\spelli.exe.txz
            cd artifacts
            xz -d spelli.exe.txz
            tar xvf spelli.exe.tar
            mv bin/spelli.exe .
        """, run_if="${{ steps.version.outputs.channel == 'nightly' }}"))
        .with_gha("installer", GithubAction("Eijebong/divvun-actions/inno-setup", {
            "path": "install.iss",
            "defines": "Version=${{ steps.version.outputs.version }}",
        }))
        .with_gha("deploy", GithubAction("Eijebong/divvun-actions/deploy", {
            "package-id": "windivvun",
            "platform": "windows",
            "payload-path": "${{ steps.installer.outputs['installer-path'] }}",
            "version": "${{ steps.version.outputs.version }}",
            "repo": "https://pahkat.uit.no/tools/",
            "channel": "${{ steps.version.outputs.channel }}",
            "windows-kind": "inno",
            "windows-product-code": "{41F71B6E-DE82-433D-8659-7E2D7C3B95E2}_is1",
        }).with_secret_input("GITHUB_TOKEN", "divvun", "github.token"))
        .find_or_create(f"build.windivvun-installer.{CONFIG.index_path}")
    )

def create_mso_build_tasks():
    matrix = [("i686-pc-windows-msvc", "vcvars32.bat", "i686"), ("x86_64-pc-windows-msvc", "vcvars64.bat", "x86_64")]
    mso_tasks = []
    for (triple, vcvars, arch) in matrix:
        mso_tasks.append((
            windows_task("MSO build: %s" % arch, clone_self=False)
            .with_rustup()
            .with_gha("clone_mso", GithubAction("actions/checkout", {
                "repository": "divvun/mso-nda-resources",
            }).with_secret_input("token", "divvun", "github.token"))
            .with_gha("setup", gha_setup())
            .with_gha("rustup", GithubAction("actions-rs/toolchain", {
                "toolchain": "stable-" + triple,
                "profile": "minimal",
                "override": "true",
            }))
            .with_gha("Set MSO CWD", GithubActionScript(f"echo ::set-cwd::%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\mso-nda-resources"))
            .with_gha("build", GithubActionScript(f"""
              cd divvunspell-mso
              set SENTRY_DSN=%INPUT_SENTRY_DSN%
              call "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\BuildTools\\VC\\Auxiliary\\Build\\{vcvars}"
              cargo build --target {triple} --release
            """).with_secret_input("SENTRY_DSN", "divvun", "MSO_DSN").with_shell("cmd"))
            .with_gha(
                "sign",
                GithubAction(
                    "Eijebong/divvun-actions/codesign",
                    {
                        "path": f"target/{triple}/release/divvunspellmso.dll"
                    },
                ),
            )
            .with_gha("artifact", GithubActionScript(f"""
                mv target/{triple}/release/divvunspellmso.dll ../
            """))
            .with_artifacts(f"divvunspellmso.dll")
            .find_or_create(f"build.windivvun-mso.{arch}.{CONFIG.index_path})"),
            arch
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
              call "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\BuildTools\\VC\\Auxiliary\\Build\\{vcvars}"
              cargo build --target {triple} --release
            """).with_shell("cmd"))
            .with_gha(
                "sign",
                GithubAction(
                    "Eijebong/divvun-actions/codesign",
                    {
                        "path": f"target/{triple}/release/windivvun.dll"
                    },
                ),
            )
            .with_gha("artifact", GithubActionScript(f"""
                mv target/{triple}/release/windivvun.dll ../../
            """))
            .with_artifacts(f"windivvun.dll")
            .find_or_create(f"build.windivvun.{arch}.{CONFIG.index_path})"),
            arch
        ))

    return windivvun_tasks



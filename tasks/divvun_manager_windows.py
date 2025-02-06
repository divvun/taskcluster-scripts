from decisionlib import CONFIG
from .common import windows_task, gha_setup, gha_pahkat, NIGHTLY_CHANNEL
from gha import GithubAction, GithubActionScript


def create_divvun_manager_windows_tasks():
    return (
        windows_task("Divvun manager (windows)")
        .with_additional_repo(
            "https://github.com/divvun/oneclick-bundler",
            "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\oneclick-bundler",
            True,
            "dotnet8"
        )
        .with_gha("setup", gha_setup())
        .with_gha(
            "setup_nugget",
            GithubAction("NuGet/setup-nuget@main", {"nuget-version": "5.x"}),
        )
        .with_script("echo $null >> ${HOME}/${TASK_ID}/_temp/github_env", as_gha=True)
        .with_gha(
            "nerdbank_version",
            GithubAction("dotnet/nbgv", {"setCommonVars": "true", "toolVersion": "3.5.119"}).with_env(
                "GITHUB_ENV", "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp\\github_env"
            ),
        )
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
            "xtask",
            GithubAction("actions-rs/cargo", {"command": "install", "args": "xargo"}),
        )
        .with_gha(
            "version",
            GithubAction(
                "divvun/taskcluster-gha/version",
                {
                    "csharp": "true",
                    "stable-channel": "beta",
                    "nightly-channel": NIGHTLY_CHANNEL,
                },
            )
            .with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN")
            .with_env(
                "GitBuildVersionSimple",
                "${{ steps.nerdbank_version.outputs.SimpleVersion }}",
            ),
        )
        .with_gha(
            "pahkat",
            gha_pahkat(
                ["pahkat-uploader", "pahkat-windows-cli", "dotnet5-webinst", "kbdi"]
            ),
        )
        .with_gha(
            "fix_csharp_paths",
            GithubActionScript(
                """
            ls $env:RUNNER_TEMP;
            ls $env:RUNNER_WORKSPACE;
            cp $env:RUNNER_TEMP\\pahkat-prefix\\pkg\\dotnet5-webinst\\bin\\dotnet5-webinst.exe $env:RUNNER_WORKSPACE\\repo\\
            cp $env:RUNNER_TEMP\\pahkat-prefix\\pkg\\dotnet5-webinst\\bin\\dotnet5-webinst.exe $env:RUNNER_WORKSPACE\\oneclick-bundler\\
            cp $env:RUNNER_TEMP\\pahkat-prefix\\pkg\\kbdi\\bin\\kbdi.exe $env:RUNNER_WORKSPACE\\oneclick-bundler\\
            cp $env:RUNNER_TEMP\\pahkat-prefix\\pkg\\kbdi\\bin\\kbdi-x64.exe $env:RUNNER_WORKSPACE\\oneclick-bundler\\
        """
            ),
        )
        .with_gha(
            "get_pahkat_service_nightly",
            GithubActionScript(
                f"""
            mkdir pahkat-config
            echo \"[\"\"https://pahkat.uit.no/divvun-installer/\"\"]`nchannel = \"\"{NIGHTLY_CHANNEL}\"\"\" > ./pahkat-config/repos.toml
            ls pahkat-config
            cat pahkat-config/repos.toml
            pahkat-windows download https://pahkat.uit.no/divvun-installer/packages/pahkat-service --output ./pahkat-service -c pahkat-config
            move pahkat-service\\* pahkat-service-setup.exe
        """,
                run_if=f"${{{{ steps.version.outputs.channel == '{NIGHTLY_CHANNEL}' }}}}",
            ),
        )
        .with_gha(
            "get_pahkat_service_stable",
            GithubActionScript(
                """
            mkdir pahkat-config
            echo \"[\"\"https://pahkat.uit.no/divvun-installer/\"\"]`nchannel = \"\"beta\"\"\" > ./pahkat-config/repos.toml
            ls pahkat-config
            cat pahkat-config/repos.toml
            pahkat-windows download https://pahkat.uit.no/divvun-installer/packages/pahkat-service --output ./pahkat-service -c pahkat-config
            move pahkat-service\\* pahkat-service-setup.exe
        """,
                run_if=f"${{{{ steps.version.outputs.channel != '{NIGHTLY_CHANNEL}' }}}}",
            ),
        )
        .with_gha(
            "msbuild",
            GithubActionScript(
                """
          "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat"
          nuget restore "Divvun.Installer.sln"
          MSBuild.exe "Divvun.Installer.sln" /p:Configuration=Release /p:Platform=x86 /m  || exit /b !ERRORLEVEL!
        """
            ).with_env(
                "GITHUB_ENV", "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp\\github_env"
            ),
        )
        .with_gha(
            "package_oneclick",
            GithubActionScript(
                """
          dotnet publish .\\Divvun.Installer.OneClick\\Divvun.Installer.OneClick.csproj /p:Platform=x86 /p:Configuration=Release
          copy Divvun.Installer.OneClick\\publish\\Divvun.Installer.OneClick.exe ../oneclick-bundler
          cd ../oneclick-bundler
          rustc -vV
          cargo -vV
          cargo xtask
        """
            ).with_env(
                "GITHUB_ENV", "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp\\github_env"
            ),
        )
        .with_gha(
            "sign_divvun_manager",
            GithubAction(
                "divvun/taskcluster-gha/codesign",
                {
                    "path": "Divvun.Installer/bin/x86/Release/net5.0-windows10.0.18362.0/win-x86/DivvunManager.exe"
                },
            ),
        )
        .with_gha(
            "sign_oneclick",
            GithubAction(
                "divvun/taskcluster-gha/codesign",
                {
                    "path": "../oneclick-bundler/target/dist/Divvun.Installer.OneClick.exe"
                },
            ),
        )
        .with_gha(
            "sign_dll",
            GithubAction(
                "divvun/taskcluster-gha/codesign",
                {
                    "path": "Divvun.Installer/bin/x86/Release/net5.0-windows10.0.18362.0/win-x86/Pahkat.Sdk.dll"
                },
            ),
        )
        .with_gha(
            "sign_dll_rpc",
            GithubAction(
                "divvun/taskcluster-gha/codesign",
                {
                    "path": "Divvun.Installer/bin/x86/Release/net5.0-windows10.0.18362.0/win-x86/Pahkat.Sdk.Rpc.dll"
                },
            ),
        )
        .with_gha(
            "installer",
            GithubAction(
                "divvun/taskcluster-gha/inno-setup",
                {
                    "path": "setup.iss",
                    "defines": "Version=${{ steps.version.outputs.version }}",
                },
            ),
        )
        .with_gha(
            "deploy_manager",
            GithubAction(
                "divvun/taskcluster-gha/deploy",
                {
                    "package-id": "divvun-installer",
                    "platform": "windows",
                    "version": "${{ steps.version.outputs.version }}",
                    "payload-path": "${{ steps.installer.outputs.installer-path }}",
                    "repo": "https://pahkat.uit.no/divvun-installer/",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "windows-kind": "inno",
                    "windows-product-code": "{4CF2F367-82A8-5E60-8334-34619CBA8347}_is1",
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "github.token"),
        )
        .with_gha(
            "deploy_installer",
            GithubAction(
                "divvun/taskcluster-gha/deploy",
                {
                    "package-id": "divvun-installer-oneclick",
                    "platform": "windows",
                    "arch": "i686",
                    "version": "${{ steps.version.outputs.version }}",
                    "payload-path": "../oneclick-bundler/target/dist/Divvun.Installer.OneClick.exe",
                    "repo": "https://pahkat.uit.no/divvun-installer/",
                    "channel": "${{ steps.version.outputs.channel }}",
                    "windows-product-code": "divvun-manager-oneclick",  # Unused but mandatory
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "github.token"),
        )
        .find_or_create(f"build.divvun-manager-windows.{CONFIG.index_path}")
    )

import os.path

from gha import GithubAction, GithubActionScript
from decisionlib import CONFIG
from .common import linux_build_task, macos_task, windows_task


def create_lang_task(with_apertium):
    if os.path.isfile(".build-config.yml"):
        print("Found config file, do something with it now")

    return (
        linux_build_task("Lang build", bundle_dest="lang")
        .with_additional_repo(
            "https://github.com/giellalt/giella-core.git", "giella-core"
        )
        .with_additional_repo(
            "https://github.com/giellalt/giella-shared.git", "giella-shared"
        )
        .with_gha(
            "deps",
            GithubAction(
                "Eijebong/divvun-actions/lang/install-deps", {"sudo": "false"}
            ),
        )
        .with_gha(
            "build", GithubAction("Eijebong/divvun-actions/lang/build", {"fst": "hfst"})
        )
        .with_named_artifacts("spellers", "./build/tools/spellcheckers/*.zhfst")
        .find_or_create(f"build.linux_x64.{CONFIG.git_sha}")
    )


def create_bundle_task(os_name, type_, lang_task_id):
    if os_name == "windows-latest":
        return (
            windows_task(f"Bundle lang: {os_name} {type_}")
            .with_git()
            .with_curl_artifact_script(lang_task_id, "spellers.tar.gz", extract=True)
            .with_gha(
                "init",
                GithubAction(
                    "Eijebong/divvun-actions/pahkat/init",
                    {
                        "repo": "https://pahkat.uit.no/devtools/",
                        "channel": "nightly",
                        "packages": "pahkat-uploader",
                    },
                ),
            )
            .with_gha(
                "setup",
                GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input(
                    "key", "divvun", "DIVVUN_KEY"
                ),
            )
            .with_gha(
                "version",
                GithubAction(
                    "Eijebong/divvun-actions/version",
                    {"speller-manifest": True, "nightly": "develop, test-ci"},
                ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
            )
            .with_gha(
                "bundle",
                GithubAction(
                    "Eijebong/divvun-actions/speller/bundle",
                    {
                        "speller-type": type_,
                        "speller-manifest-path": "manifest.toml",
                        "speller-path": "${{ steps.build.outputs['speller-paths'] }}",
                        "version": "${{ steps.version.outputs.version }}",
                    },
                ).with_outputs_from(lang_task_id),
            )
            .find_or_create(f"bundle.{os_name}_x64_{type_}.{CONFIG.git_sha}")
        )

    if os_name == "macos-latest":
        return (
            macos_task(f"Bundle lang: {os_name} {type_}")
            .with_curl_artifact_script(lang_task_id, "spellers.tar.gz", extract=True)
            .with_gha(
                "init",
                GithubAction(
                    "Eijebong/divvun-actions/pahkat/init",
                    {
                        "repo": "https://pahkat.uit.no/devtools/",
                        "channel": "nightly",
                        "packages": "pahkat-uploader, divvun-bundler, thfst-tools, xcnotary",
                    },
                ),
            )
            .with_gha(
                "setup",
                GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input(
                    "key", "divvun", "DIVVUN_KEY"
                ),
            )
            .with_gha(
                "version",
                GithubAction(
                    "Eijebong/divvun-actions/version",
                    {"speller-manifest": True, "nightly": "develop, test-ci"},
                ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
            )
            .with_gha(
                "bundle",
                GithubAction(
                    "Eijebong/divvun-actions/speller/bundle",
                    {
                        "speller-type": type_,
                        "speller-manifest-path": "manifest.toml",
                        "speller-path": "${{ steps.build.outputs['speller-paths'] }}",
                        "version": "${{ steps.version.outputs.version }}",
                    },
                ).with_outputs_from(lang_task_id),
            )
            .find_or_create(f"bundle.{os_name}_x64_{type_}.{CONFIG.git_sha}")
        )

    raise NotImplementedError

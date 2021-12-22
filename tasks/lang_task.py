from .common import linux_build_task, macos_task, windows_task
from .gha import GithubAction
from decisionlib import CONFIG
import os.path


def create_lang_task(with_apertium):
    if os.path.isfile(".build-config.yml"):
        print("Found config file, do something with it now")

    return (
        linux_build_task("Lang build", bundle_dest="lang")
        .with_additional_repo(
            "https://github.com/giellalt/giella-core.git", "../giella-core"
        )
        .with_additional_repo(
            "https://github.com/giellalt/giella-shared.git", "../giella-shared"
        )
        .with_gha('deps', GithubAction("Eijebong/divvun-actions/lang/install-deps", {"sudo": "false"}))
        .with_gha('build', GithubAction("Eijebong/divvun-actions/lang/build", {"fst": "hfst"}))
        .with_prep_gha_tasks()
        .with_named_artifacts("spellers", "./build/tools/spellcheckers/*.zhfst")
        .find_or_create("build.linux_x64.%s" % CONFIG.git_sha)
    )


def create_bundle_task(os, type_, lang_task_id):
    if os == "windows-latest":
        return (
            windows_task("Bundle lang: %s %s" % (os, type_))
            .with_git()
            .with_curl_artifact_script(lang_task_id, "spellers.tar.gz", extract=True)
            .with_gha("init", GithubAction("Eijebong/divvun-actions/pahkat/init", {"repo": "https://pahkat.uit.no/devtools/", "channel": "nightly", "packages": "pahkat-uploader" }))
            .with_gha("setup", GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input("key", "divvun", "DIVVUN_KEY"))
            .with_gha("version", GithubAction("Eijebong/divvun-actions/version", {"speller-manifest": True, "nightly": "develop, test-ci"}).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"))
            .with_gha("bundle", GithubAction("Eijebong/divvun-actions/speller/bundle", {"speller-type": type_, "speller-manifest-path": "manifest.toml"}).with_mapped_output("speller-paths", "build", "speller-paths", task_id=lang_task_id).with_mapped_output("version", "version", "version"))
            .with_prep_gha_tasks()
            .find_or_create("bundle.%s_x64_%s.%s" % (os, type_, CONFIG.git_sha))
        )
    elif os == "macos-latest":
        return (
            macos_task("Bundle lang: %s %s" % (os, type_))
            .with_curl_artifact_script(lang_task_id, "spellcheckers.bundle.tar.gz")
            .with_gha("init", GithubAction("Eijebong/divvun-actions/pahkat/init", {"repo": "https://pahkat.uit.no/devtools/", "channel": "nightly", "packages": "pahkat-uploader, divvun-bundler, thfst-tools, xcnotary" }))
            .with_gha("setup", GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input("key", "divvun", "DIVVUN_KEY"))
            .with_gha("version", GithubAction("Eijebong/divvun-actions/version", {"speller-manifest": True, "nightly": "develop, test-ci"}).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"))
            .with_gha("bundle", GithubAction("Eijebong/divvun-actions/speller/bundle", {"speller-type": type_, "speller-manifest-path": "manifest.toml"}).with_mapped_output("speller-paths", "build", "speller-paths", task_id=lang_task_id).with_mapped_output("version", "version", "version"))
            .find_or_create("bundle.%s_x64_%s.%s" % (os, type_, CONFIG.git_sha))
        )
    else:
        raise NotImplemented

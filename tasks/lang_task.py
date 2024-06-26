from gha import GithubAction, GithubActionScript
from decisionlib import CONFIG
from .common import linux_build_task, macos_task, windows_task, NIGHTLY_CHANNEL, gha_setup

NO_DEPLOY_LANG = {
    "zxx",  # No linguistic data
    "sjd",
    "est-x-plamk",
    "nno-x-ext-apertium",
}

INSTALL_APERTIUM_LANG = {
    "hil",
}


def create_lang_tasks(repo_name):
    should_install_apertium = (
        repo_name.endswith("apertium")
        or repo_name[len("lang-"):] in INSTALL_APERTIUM_LANG
    )

    should_build_analysers = CONFIG.tc_config.get(
        'build', {}).get('analysers', False)
    should_build_spellers = CONFIG.tc_config.get(
        'build', {}).get('spellers', False)
    should_build_grammar_checkers = CONFIG.tc_config.get(
        'build', {}).get('grammar-checkers', False)

    previous_task_id = None
    speller_task_id = None

    if should_build_analysers:
        previous_task_id = create_analysers_task(should_install_apertium)

    if should_build_spellers:
        previous_task_id = create_spellers_task(previous_task_id)
        speller_task_id = previous_task_id

    if should_build_grammar_checkers:
        previous_task_id = create_grammar_checkers_task(previous_task_id)

    # index_read_only means this is a PR and shouldn't run deployment steps
    if repo_name[len("lang-"):] in NO_DEPLOY_LANG or CONFIG.index_read_only:
        return

    for os_, type_ in [
        ("macos-latest", "speller-macos"),
        ("macos-latest", "speller-mobile"),
        ("windows-latest", "speller-windows"),
    ]:
        create_bundle_task(os_, type_, speller_task_id)


def create_analysers_task(with_apertium):
    should_check_analysers = CONFIG.tc_config.get(
        'check', {}).get('analysers', False)
    if should_check_analysers:
        task_name = "Build & check analysers"
    else:
        task_name = "Build analysers"
    task_suffix = "-analysers"

    return (
        base_lang_task(task_name, with_apertium)
        .with_gha(
            "build_analysers",
            GithubAction(
                "divvun/taskcluster-gha/lang/build",
                {
                    "fst": "hfst",
                    "analysers": "true",
                    "spellers": "false"
                }
            )
        )
        .with_gha(
            "check_analysers",
            GithubAction(
                "divvun/taskcluster-gha/lang/check", {}
            ), enabled=should_check_analysers
        )
        .find_or_create(f"build.linux_x64.{CONFIG.index_path}{task_suffix}")
    )


def create_spellers_task(dependent_task_id):
    should_check_spellers = CONFIG.tc_config.get(
        'check', {}).get('spellers', False)
    if should_check_spellers:
        task_name = "Build & check spellers"
    else:
        task_name = "Build spellers"
    task_suiffix = "-spellers"

    return (
        base_lang_task(task_name)
        .with_dependencies(dependent_task_id)
        .with_gha(
            "build_spellers",
            GithubAction(
                "divvun/taskcluster-gha/lang/build",
                {"fst": "hfst", "spellers": "true"}
            )
        )
        .with_gha(
            "check_spellers", GithubAction(
                "divvun/taskcluster-gha/lang/check", {}
            ), enabled=should_check_spellers
        )
        .with_named_artifacts(
            "spellers",
            "${HOME}/tasks/${TASK_ID}/lang/build/tools/spellcheckers/*.zhfst",
        )
        .find_or_create(f"build.linux_x64.{CONFIG.index_path}{task_suiffix}")
    )


def create_grammar_checkers_task(dependent_task_id):
    should_check_grammar_checkers = CONFIG.tc_config.get(
        'check', {}).get('grammar-checkers', False)
    if should_check_grammar_checkers:
        task_name = "Build & check grammar checkers"
    else:
        task_name = "Build grammar checkers"
    task_suffix = "-grammar-checkers"

    return (
        base_lang_task(task_name)
        .with_dependencies(dependent_task_id)
        .with_gha(
            "build_grammar-checkers",
            GithubAction(
                "divvun/taskcluster-gha/lang/build",
                {"fst": "hfst", "grammar-checkers": "true"}
            )
        )
        .with_gha(
            "check_grammar-checkers",
            GithubAction(
                "divvun/taskcluster-gha/lang/check", {}
            ), enabled=should_check_grammar_checkers
        )
        .find_or_create(f"build.linux_x64.{CONFIG.index_path}{task_suffix}")
    )


def base_lang_task(task_name, with_apertium=False):
    return (
        linux_build_task(task_name, bundle_dest="lang")
        .with_additional_repo(
            "https://github.com/giellalt/giella-core.git",
            "${HOME}/tasks/${TASK_ID}/giella-core",
        )
        .with_additional_repo(
            "https://github.com/giellalt/giella-shared.git",
            "${HOME}/tasks/${TASK_ID}/giella-shared",
        )
        .with_additional_repo(
            "https://github.com/giellalt/shared-eng",
            "${HOME}/tasks/${TASK_ID}/shared-eng"
        )
        .with_additional_repo(
            "https://github.com/giellalt/shared-urj-Cyrl",
            "${HOME}/tasks/${TASK_ID}/shared-urj-Cyrl"
        )
        .with_additional_repo(
            "https://github.com/giellalt/shared-smi",
            "${HOME}/tasks/${TASK_ID}/shared-smi"
        )
        .with_additional_repo(
            "https://github.com/giellalt/shared-mul",
            "${HOME}/tasks/${TASK_ID}/shared-mul"
        )
        .with_gha(
            "deps",
            GithubAction(
                "divvun/taskcluster-gha/lang/install-deps",
                {"sudo": "false", "apertium": with_apertium},
            ),
        )
    )


def create_bundle_task(os_name, type_, lang_task_id):
    if os_name == "windows-latest":
        return (
            windows_task(f"Bundle lang: {type_}")
            .with_git()
            .with_curl_artifact_script(
                lang_task_id, "spellers.tar.gz", extract=True, as_gha=True
            )
            .with_gha(
                "init",
                GithubAction(
                    "divvun/taskcluster-gha/pahkat/init",
                    {
                        "repo": "https://pahkat.uit.no/devtools/",
                        "channel": NIGHTLY_CHANNEL,
                        "packages": "pahkat-uploader",
                    },
                ),
            )
            .with_gha("setup", gha_setup())
            .with_gha(
                "version",
                GithubAction(
                    "divvun/taskcluster-gha/version",
                    {
                        "speller-manifest": True,
                        "nightly-channel": NIGHTLY_CHANNEL,
                        "insta-stable": "true",
                    },
                ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
            )
            .with_gha(
                "bundler",
                GithubAction(
                    "divvun/taskcluster-gha/speller/bundle",
                    {
                        "speller-type": type_,
                        "speller-manifest-path": "manifest.toml",
                        "speller-paths": "${{ steps.build_spellers.outputs['speller-paths'] }}",
                        "version": "${{ steps.version.outputs.version }}",
                    },
                ).with_outputs_from(lang_task_id),
            )
            .with_gha(
                "deploy",
                GithubAction(
                    "divvun/taskcluster-gha/speller/deploy",
                    {
                        "speller-type": type_,
                        "speller-manifest-path": "manifest.toml",
                        "payload-path": "${{ steps.bundler.outputs['payload-path'] }}",
                        "version": "${{ steps.version.outputs.version }}",
                        "channel": "${{ steps.version.outputs.channel }}",
                        "repo": "https://pahkat.uit.no/main/",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ),
            )
            .find_or_create(f"bundle.{os_name}_x64_{type_}.{CONFIG.index_path}")
        )

    if os_name == "macos-latest":
        return (
            macos_task(f"Bundle lang: {type_}")
            .with_curl_artifact_script(
                lang_task_id, "spellers.tar.gz", extract=True, as_gha=True
            )
            .with_gha(
                "init",
                GithubAction(
                    "divvun/taskcluster-gha/pahkat/init",
                    {
                        "repo": "https://pahkat.uit.no/devtools/",
                        "channel": NIGHTLY_CHANNEL,
                        "packages": "pahkat-uploader, divvun-bundler, thfst-tools, xcnotary",
                    },
                ),
            )
            .with_gha(
                "setup",
                GithubAction(
                    "divvun/taskcluster-gha/setup", {}
                ).with_secret_input(
                    "key", "divvun", "DIVVUN_KEY"
                ),
            )
            .with_gha(
                "version",
                GithubAction(
                    "divvun/taskcluster-gha/version",
                    {
                        "speller-manifest": True,
                        "nightly-channel": NIGHTLY_CHANNEL,
                        "insta-stable": "true",
                    },
                ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
            )
            .with_gha(
                "bundler",
                GithubAction(
                    "divvun/taskcluster-gha/speller/bundle",
                    {
                        "speller-type": type_,
                        "speller-manifest-path": "manifest.toml",
                        "speller-paths": "${{ steps.build_spellers.outputs['speller-paths'] }}",
                        "version": "${{ steps.version.outputs.version }}",
                    },
                ).with_outputs_from(lang_task_id),
            )
            .with_gha(
                "deploy",
                GithubAction(
                    "divvun/taskcluster-gha/speller/deploy",
                    {
                        "speller-type": type_,
                        "speller-manifest-path": "manifest.toml",
                        "payload-path": "${{ steps.bundler.outputs['payload-path'] }}",
                        "version": "${{ steps.version.outputs.version }}",
                        "channel": "${{ steps.version.outputs.channel }}",
                        "repo": "https://pahkat.uit.no/main/",
                        "nightly-channel": NIGHTLY_CHANNEL,
                    },
                ),
            )
            .find_or_create(f"bundle.{os_name}_x64_{type_}.{CONFIG.index_path}")
        )

    raise NotImplementedError

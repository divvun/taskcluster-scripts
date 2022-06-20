from .common import macos_task, linux_build_task, windows_task, NIGHTLY_CHANNEL
from gha import GithubAction, GithubActionScript
from decisionlib import CONFIG


def create_omegat_tasks():
    return (linux_build_task("OmegaT plugin linux build")
        .with_apt_install("ant", "autoconf", "gcc", "libtool")
        .with_gha(
            "clone_jna",
            GithubAction(
                "actions/checkout",
                {
                    "repository": "lenguyenthanh/jna",
                    "path": "${HOME}/tasks/${TASK_ID}/repo/jna",
                    "fetch-depth": 0,
                },
                enable_post=False,
            ).with_secret_input("token", "divvun", "github.token"),
        )
        .with_gha(
            "clone_sdk",
            GithubAction(
                "actions/checkout",
                {
                    "repository": "divvun/divvunspell-sdk-java",
                    "path": "${HOME}/tasks/${TASK_ID}/repo/sdk",
                    "fetch-depth": 0,
                    "ref": "poc-for-divvun-omegaT",
                },
                enable_post=False,
            ).with_secret_input("token", "divvun", "github.token"),
        )
        .with_gha(
            "java",
            GithubAction(
                "actions/setup-java@v2",
                {"distribution": "temurin", "java-version": "8"},
            ),
        )
        .with_gha("build_jna", GithubActionScript("""
            cd jna
            ant javah
            ant native
            ant jar
            cp ./build/jna-jpms.jar ../sdk/libs/jna.jar
        """))
        .with_gha("build_sdk", GithubActionScript("""
            cd sdk
            ./gradlew
            cp build/divvun.jar ../libs/divvun.jar
        """))
        .with_gha("build_plugin", GithubActionScript("""
            ./gradlew
        """))
        .find_or_create(f"build.omegat.linux.{CONFIG.index_path}"))


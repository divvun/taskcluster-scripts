from .common import NIGHTLY_CHANNEL, task_builder_for
from gha import GithubAction, GithubActionScript
from decisionlib import CONFIG


def create_omegat_tasks():
    for os_ in ("linux", "macos", "windows"):
        task = task_builder_for(os_)(f"OmegaT plugin {os_} build")
        if os_ == "linux":
            task.with_apt_install("ant", "autoconf", "gcc", "libtool", "texinfo")
        if os_ == "windows":
            task.with_directory_mount("https://archive.apache.org/dist/ant/binaries/apache-ant-1.10.0-bin.zip", path="ant").with_path_from_homedir("ant\\bin")

        (task
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
                bash ./build.sh
                cp ./build/jna-jpms.jar ../sdk/libs/jna.jar
            """))
            .with_gha("build_sdk", GithubActionScript("""
                cd sdk
                ./gradlew build
                cp build/libs/divvunspell-sdk-java*.jar ../libs/divvun.jar
            """))
            .with_gha("build_plugin", GithubActionScript("""
                ./gradlew build
            """))
            .find_or_create(f"build.omegat.{os_}.{CONFIG.index_path}"))


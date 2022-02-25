from gha import GithubAction, GithubActionScript
from decisionlib import CONFIG
from .common import macos_task, gha_setup, gha_pahkat


def create_divvun_keyboard_tasks():
    create_ios_keyboard_task()
    create_android_keyboard_task()


def create_android_keyboard_task():
    return (
        macos_task(f"Build keyboard: Android")
        .with_gha("setup", gha_setup())
        .with_gha("init", gha_pahkat(["kbdgen"]))
        .with_gha(
            "java",
            GithubAction(
                "actions/setup-java@v2",
                {"distribution": "temurin", "java-version": "11"},
            ),
        )
        .with_gha(
            "build",
            GithubAction(
                "Eijebong/divvun-actions/keyboard/build-meta",
                {"keyboard-type": "keyboard-android", "bundle-path": "divvun.kbdgen"},
            ),
        )
        .with_gha(
            "publish",
            GithubActionScript(
                """
                cd output/deps/giella-ime
                ./gradlew publishApk
            """
            )
            .with_env("SPACESHIP_SKIP_2FA_UPGRADE", 1)
            .with_env("LANG", "en_US.UTF-8"),
            enabled=(CONFIG.git_ref == "refs/heads/master"),
        )
        .find_or_create(f"keyboard-build.ios.{CONFIG.index_path}")
    )


def create_ios_keyboard_task():
    return (
        macos_task(f"Build keyboard: IOS")
        .with_gha("setup", gha_setup())
        .with_gha("init", gha_pahkat(["kbdgen"]))
        .with_gha(
            "build",
            GithubAction(
                "Eijebong/divvun-actions/keyboard/build-meta",
                {"keyboard-type": "keyboard-ios", "bundle-path": "divvun.kbdgen"},
            ),
        )
        .with_gha(
            "publish",
            GithubActionScript(
                """
            fastlane pilot upload --api_key_path "$DIVVUN_CI_CONFIG/enc/creds/macos/appstore-key.json" --skip_submission --skip_waiting_for_build_processing --ipa "output/ios-build/ipa/Divvun Keyboards.ipa"
            """
            )
            .with_env("SPACESHIP_SKIP_2FA_UPGRADE", 1)
            .with_env("LANG", "en_US.UTF-8"),
            enabled=(CONFIG.git_ref == "refs/heads/master"),
        )
        .find_or_create(f"keyboard-build.ios.{CONFIG.index_path}")
    )

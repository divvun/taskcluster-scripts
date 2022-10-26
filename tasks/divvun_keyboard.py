from gha import GithubAction, GithubActionScript
from decisionlib import CONFIG
from .common import macos_task, gha_setup, gha_pahkat


def create_divvun_keyboard_tasks(bundle, is_dev):
    create_ios_keyboard_task(bundle, is_dev)
    create_android_keyboard_task(bundle)


def create_android_keyboard_task(bundle):
    return (
        macos_task(f"Build keyboard: Android")
        .with_env(**{"ANDROID_HOME": "/Users/admin/android-sdk"})
        .with_gha("setup", gha_setup())
        .with_gha("init", gha_pahkat(["kbdgen@2.0.0-nightly.20210622T210632Z"]))
        .with_gha(
            "build",
            GithubAction(
                "Eijebong/divvun-actions/keyboard/build-meta",
                {"keyboard-type": "keyboard-android", "bundle-path": bundle},
            ),
        )
        .with_gha(
            "publish",
            GithubActionScript(
                """
                source ${DIVVUN_CI_CONFIG}/enc/env.sh
                cd output/deps/giella-ime
                ./gradlew publishApk
            """
            )
            .with_env("SPACESHIP_SKIP_2FA_UPGRADE", 1)
            .with_env("LANG", "en_US.UTF-8"),
            enabled=(CONFIG.git_ref == "refs/heads/main"),
        )
        .find_or_create(f"keyboard-build.android.{CONFIG.index_path}")
    )


def create_ios_keyboard_task(bundle, is_dev):
    ipa_name = "Divvun Keyboards.ipa"
    if is_dev:
        ipa_name = "Divvun Dev Keyboards.ipa"
    return (
        macos_task(f"Build keyboard: IOS")
        .with_gha("setup", gha_setup())
        .with_gha("init", gha_pahkat(["kbdgen"]))
        .with_gha(
            "build",
            GithubAction(
                "Eijebong/divvun-actions/keyboard/build-meta",
                {"keyboard-type": "keyboard-ios", "bundle-path": bundle},
            ),
        )
        .with_gha(
            "publish",
            GithubActionScript(
                """
            fastlane pilot upload --api_key_path "${DIVVUN_CI_CONFIG}/enc/creds/macos/appstore-key.json" --skip_submission --skip_waiting_for_build_processing --ipa "output/ios-build/ipa/%s"
            """
                % ipa_name
            )
            .with_env("SPACESHIP_SKIP_2FA_UPGRADE", 1)
            .with_env("LANG", "en_US.UTF-8")
            .with_env("ITMSTRANSPORTER_FORCE_ITMS_PACKAGE_UPLOAD", "true"),
            enabled=(CONFIG.git_ref == "refs/heads/main"),
        )
        .find_or_create(f"keyboard-build.ios.{CONFIG.index_path}")
    )

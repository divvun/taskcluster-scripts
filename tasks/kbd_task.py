from .common import macos_task, windows_task
from .gha import GithubAction
from decisionlib import CONFIG

def create_kbd_task(os):
    if os == "windows-latest":
        return (
        windows_task("Build keyboard: %s" % os)
            .with_git()
            .with_gha("setup", GithubAction("Eijebong/divvun-actions/setup", {}).with_secret_input("key", "divvun", "DIVVUN_KEY"))
            .with_gha("init", GithubAction("Eijebong/divvun-actions/pahkat/init", {"repo": "https://pahkat.uit.no/devtools/", "channel": "nightly", "packages": "pahkat-uploader, kbdgen" }))
            .with_gha("build", GithubAction("Eijebong/divvun-actions/keyboard/build", {"keyboard-type": "keyboard-windows"}))
            .with_prep_gha_tasks()
            .find_or_create("bundle.%s_x64.%s" % (os, CONFIG.git_sha))
        )
    elif os == "macos-latest":
        return
        return (
            macos_task("Bundle lang: %s %s" % (os, type_))
            .with_curl_artifact_script(lang_task_id, "spellcheckers.bundle.tar.gz")
            .find_or_create("bundle.%s_x64_%s.%s" % (os, type_, CONFIG.git_sha))
        )
    else:
        raise NotImplemented

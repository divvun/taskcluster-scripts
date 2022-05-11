from decisionlib import CONFIG
from gha import GithubAction, GithubActionScript
from .common import (
    macos_task,
    gha_setup,
    gha_pahkat,
    PAHKAT_REPO,
    NIGHTLY_CHANNEL,
    generic_rust_build_upload_task,
    RUST_ENV,
)

def create_mso_resources_tasks():
    create_patch_gen_task()

def create_patch_gen_task():
    (macos_task("Generate MSO patches")
        .with_gha("setup", gha_setup())
        .with_gha("install_rustup", GithubAction("actions-rs/toolchain", {"toolchain": "nightly", "overried": "true"}))
        .with_gha("build_patcher", GithubActionScript("cd mso-patcher && npm install && npm run build"))
        .with_gha("download_office", GithubActionScript(r"""
          for MSO_URL in $(node mso-patcher/dist/unpatched.js); do
              export MSO_VER=$(echo $MSO_URL | sed -e 's/https:\/\/officecdn-microsoft-com.akamaized.net\/pr\/C1297A47-86C4-4C1F-97FA-950631F94777\/MacAutoupdate\/Microsoft_Word_\(.*\)_Installer\.pkg/\1/')
              echo $MSO_URL
              wget -o mso.pkg "$MSO_URL"
              installer -verbose -pkg mso.pkg -target /
              rm -f mso.pkg
              sudo mv "/Applications/Microsoft Word.app" $MSO_VER
              echo $MSO_VER
          done
          """))
        .with_gha("build_rust", GithubAction("actions-rs/cargo", {"command": "build"}))
        .find_or_create(f"build.mso_resources.patches.{CONFIG.index_path}"))


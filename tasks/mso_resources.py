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
    create_lang_bundler_task()

def create_lang_bundler_task():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Lang bundler build",
        "divvun-bundler-mso/Cargo.toml",
        package_id="divvun-bundler",
        target_dir="target",
        only_os=["macos"],
        bin_name="divvun-bundler-mso",
        rename_binary="divvun-bundler",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )


def create_mso_patch_gen_task():
    (
        macos_task("Generate MSO patches")
        .with_max_run_time_minutes(600)
        .with_gha("setup", gha_setup())
        .with_gha("setup_git", GithubActionScript("""
            git config user.email "feedback@divvun.no"
            git config user.name "divvunbot"
        """))
        .with_gha(
            "install_rustup",
            GithubAction(
                "actions-rs/toolchain",
                {
                    "toolchain": "nightly",
                    "override": "true",
                    "target": "aarch64-apple-darwin",
                },
            ),
        )
        .with_gha(
            "build_patcher",
            GithubActionScript("cd mso-patcher && npm install && npm run build"),
        )
        .with_gha(
            "build_rust",
            GithubAction(
                "actions-rs/cargo", {"command": "build", "args": "--release"}
            ).with_env("SENTRY_DSN", "${{ secrets.divvun.MSO_MACOS_DSN }}"),
        )
        .with_gha(
            "build_rust_aarch64",
            GithubAction(
                "actions-rs/cargo",
                {"command": "build", "args": "--release --target aarch64-apple-darwin"},
            ).with_env("SENTRY_DSN", "${{ secrets.divvun.MSO_MACOS_DSN }}"),
        )
        .with_gha(
            "version",
            GithubAction(
                "divvun/taskcluster-gha/version",
                {
                    "cargo": "divvunspell-mso/Cargo.toml",
                    "nightly-channel": NIGHTLY_CHANNEL,
                },
            ).with_secret_input("GITHUB_TOKEN", "divvun", "GITHUB_TOKEN"),
        )
        .with_gha(
            "create_patches",
            GithubActionScript(
                r"""
          mkdir -p mso
          for MSO_URL in $(node mso-patcher/dist/unpatched.js); do
              export MSO_VER=$(echo $MSO_URL | sed -e 's/https:\/\/officecdn.microsoft.com\/pr\/C1297A47-86C4-4C1F-97FA-950631F94777\/MacAutoupdate\/Microsoft_Office_\(.*\)_Installer\.pkg/\1/')
              echo $MSO_URL
              wget -O mso.pkg "$MSO_URL"
              sudo installer -allowUntrusted -verbose -pkg mso.pkg -target / || continue
              rm -f mso.pkg
              ls /Applications
              sudo mv "/Applications/Microsoft Word.app" mso/$MSO_VER
              sudo chmod -R 777 mso/$MSO_VER
              ./target/release/divvun-bundler-mso -V $VERSION \
              -o patches \
              -R -a "Developer ID Application: The University of Tromso (2K5J2584NX)" -i "Developer ID Installer: The University of Tromso (2K5J2584NX)" \
              -n "$DEVELOPER_ACCOUNT" -p "$DEVELOPER_PASSWORD" \
              -H "Divvunspell MSOffice" -t osx msoffice_patch \
              --lib ./libdivvunspellmso.dylib \
              --mso $PWD/mso/$MSO_VER
              rm -Rf $PWD/mso/$MSO_VER
          done
          """
            )
            .with_env("VERSION", "${{ steps.version.outputs.version }}")
            .with_env("SENTRY_DSN", "${{ secrets.divvun.MSO_MACOS_DSN }}")
            .with_env(
                "DEVELOPER_ACCOUNT", "${{ secrets.divvun.macos.developerAccountMacos }}"
            )
            .with_env(
                "DEVELOPER_PASSWORD", "${{ secrets.divvun.macos.appPasswordMacos }}"
            )
        )
        .with_gha("create_commit", GithubActionScript("""
            git add patches/install
            git add patches/uninstall
            git commit -m "[CD] Refresh patches" || exit 0
            git clean -fdx
        """))
        .with_gha("create_mr", GithubAction("peter-evans/create-pull-request@v4", {
            "branch": "refresh-patches",
            "title": "Refresh MSO patches",
            "body": "",
            "author": "divvunbot <feedback@divvun.no>",
            "path": "repo",
        }).with_secret_input("token", "divvun", "github.token"))
        .find_or_create(f"build.mso_resources.patches.{CONFIG.index_path}")
    )

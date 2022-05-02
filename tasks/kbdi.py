from .common import (
    gha_pahkat,
    generic_rust_task,
    generic_rust_build_upload_task,
    RUST_ENV,
)
from decisionlib import CONFIG
from gha import GithubAction


def create_kbdi_tasks():
    create_kbdi_deploy_task()
    create_kbdi_legacy_deploy_task()


def create_kbdi_deploy_task():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Kbdi build",
        "Cargo.toml",
        get_features=lambda _: "--bin kbdi",
        package_id="kbdi",
        target_dir="target",
        only_os=["windows_3264"],
        bin_name="kbdi",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )


def create_kbdi_legacy_deploy_task():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Kbdi legacy build",
        "Cargo.toml",
        get_features=lambda _: "--bin kbdi-legacy --features legacy",
        package_id="kbdi-legacy",
        target_dir="target",
        only_os=["windows"],
        bin_name="kbdi-legacy",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )

from .common import gha_pahkat, generic_rust_task, generic_rust_build_upload_task
from decisionlib import CONFIG
from gha import GithubAction

RUST_ENV = {
    "RUST_VERSION": "stable",
    "CARGO_INCREMENTAL": "0",
    "RUSTUP_MAX_RETRIES": "10",
    "CARGO_NET_RETRY": "10",
    "RUST_BACKTRACE": "full",
    "LZMA_API_STATIC": "1",
}


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
        get_features=lambda _: "--bin kbdi-legacy",
        package_id="kbdi-legacy",
        target_dir="target",
        only_os=["windows"],
        bin_name="kbdi-legacy",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )

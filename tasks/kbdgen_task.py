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


def create_kbdgen_tasks():
    create_kbdgen_deploy_tasks()


def create_kbdgen_deploy_tasks():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Kbdgen2 build",
        "Cargo.toml",
        package_id="kbdgen2",
        target_dir="target",
        bin_name="kbdgen",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )

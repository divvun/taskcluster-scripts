from .common import (
    gha_pahkat,
    generic_rust_task,
    generic_rust_build_upload_task,
    RUST_ENV,
)
from decisionlib import CONFIG
from gha import GithubAction


def create_kbdgen_tasks():
    create_kbdgen_deploy_tasks()


def create_kbdgen_deploy_tasks():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Kbdgen build",
        "Cargo.toml",
        package_id="kbdgen",
        target_dir="target",
        bin_name="kbdgen",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )

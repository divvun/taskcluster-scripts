from .common import gha_pahkat, generic_rust_task, generic_rust_build_upload_task
from gha import GithubAction

RUST_ENV = {
    "RUST_VERSION": "stable",
    "CARGO_INCREMENTAL": "0",
    "RUSTUP_MAX_RETRIES": "10",
    "CARGO_NET_RETRY": "10",
    "RUST_BACKTRACE": "full",
    "LZMA_API_STATIC": "1",
}


def create_gut_tasks():
    create_gut_test_tasks()
    create_gut_lint_tasks()
    create_gut_deploy_tasks()


def create_gut_lint_tasks():
    def add_lints(task):
        return task.with_gha(
            GithubAction(
                "actions-rs/cargo", {"command": "clippy", "args": "-- -D warnings"}
            )
        ).with_gha(
            GithubAction(
                "actions-rs/cargo", {"command": "fmt", "args": "--all -- --check"}
            )
        )

    return generic_rust_task("Gut lints", add_lints)


def create_gut_test_tasks():
    def add_lints(task):
        return task.with_gha(GithubAction("actions-rs/cargo", {"command": "test"}))

    return generic_rust_task("Gut lints", add_lints)


def create_gut_deploy_tasks():
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Gut",
        "Cargo.toml",
        package_id="gut",
        target_dir="target",
        bin_name="gut",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
    )

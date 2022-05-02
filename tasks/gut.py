from .common import (
    gha_pahkat,
    generic_rust_task,
    generic_rust_build_upload_task,
    RUST_ENV,
)
from decisionlib import CONFIG
from gha import GithubAction


def create_gut_tasks():
    test_tasks = create_gut_test_tasks()
    create_gut_lint_tasks()

    if CONFIG.index_read_only:
        return

    # Branch only tasks
    create_gut_deploy_tasks(test_tasks)


def create_gut_lint_tasks():
    def add_lints(task):
        return task.with_gha(
            "clippy",
            GithubAction(
                "actions-rs/cargo", {"command": "clippy", "args": "-- -D warnings"}
            ),
        ).with_gha(
            "fmt",
            GithubAction(
                "actions-rs/cargo", {"command": "fmt", "args": "--all -- --check"}
            ),
        )

    return generic_rust_task("gut.lints", "Gut lints", add_lints)


def create_gut_test_tasks():
    def add_lints(task):
        return task.with_gha(
            "test", GithubAction("actions-rs/cargo", {"command": "test"})
        )

    return generic_rust_task("gut.tests", "Gut tests", add_lints)


def create_gut_deploy_tasks(depends_on):
    setup_uploader = lambda _: gha_pahkat(["pahkat-uploader"])

    return generic_rust_build_upload_task(
        "Gut build",
        "Cargo.toml",
        package_id="gut",
        target_dir="target",
        bin_name="gut",
        env=RUST_ENV,
        setup_uploader=setup_uploader,
        depends_on=depends_on,
    )

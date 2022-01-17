# Copyright 2018 The Servo Project Developers. See the COPYRIGHT
# file at the top-level directory of this distribution.
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""
This file contains helpers to create taskcluster tasks. It is heavily inspired
by servo's decisionlib and reuses some of its code. Note that unlike servo's
decisionlib, this is very much targetted at divvun's usage and running github
actions on taskcluster instead of being generic.
"""

import collections
import contextlib
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Set, Optional, Tuple
import taskcluster
import gha
import utils


# Public API
__all__ = [
    "CONFIG",
    "SHARED",
    "Task",
    "DockerWorkerTask",
    "GenericWorkerTask",
    "WindowsGenericWorkerTask",
    "MacOsGenericWorkerTask",
    "make_repo_bundle",
]


class Config:
    """
    Global configuration, for users of the library to modify.
    """

    def __init__(self):
        self.task_name_template = "Divvun: %s"
        self.index_prefix = "project.divvun"
        self.index_read_only = False
        self.scopes_for_all_subtasks: List[str] = []
        self.routes_for_all_subtasks: List[str] = []
        self.repacked_msi_files_expire_in = "1 month"

        # Set by docker-worker:
        # https://docs.taskcluster.net/docs/reference/workers/docker-worker/docs/environment
        self.decision_task_id = os.environ["TASK_ID"]
        self.run_id = os.environ["RUN_ID"]

        # Set in the decision task’s payload, such as defined in .taskcluster.yml
        self.task_owner = os.environ.get("TASK_OWNER")
        self.task_source = os.environ.get("TASK_SOURCE")
        self.git_url = os.environ.get("GIT_URL")
        self.git_ref = os.environ.get("GIT_REF")
        self.git_sha = os.environ.get("GIT_SHA")
        self.git_bundle_shallow_ref = "refs/heads/shallow"

        self.tc_root_url = os.environ.get("TASKCLUSTER_ROOT_URL")
        self.default_provisioner_id = "divvun"
        self._tree_hash = None

    def tree_hash(self) -> str:
        if self._tree_hash is None:
            # Use the SHA-1 hash of the git "tree" object rather than the commit.
            # A `@bors-servo retry` command creates a new merge commit with a different commit hash
            # but with the same tree hash.
            output = subprocess.check_output(
                ["git", "show", "-s", "--format=%T", "HEAD"]
            )
            self._tree_hash = output.decode("utf-8").strip()
        return self._tree_hash

    def git_sha_is_current_head(self):
        output = subprocess.check_output(["git", "rev-parse", "HEAD"])
        self.git_sha = output.decode("utf8").strip()


class Shared:
    """
    Global shared state.
    """

    def __init__(self):
        self.now = datetime.datetime.utcnow()
        self.found_or_created_indexed_tasks: Dict[str, str] = {}

        options = {"rootUrl": os.environ["TASKCLUSTER_PROXY_URL"]}
        self.queue_service = taskcluster.Queue(options)
        self.index_service = taskcluster.Index(options)

    def from_now_json(self, offset):
        """
        Same as `taskcluster.fromNowJSON`, but uses the creation time of `self` for “now”.
        """
        return taskcluster.stringDate(taskcluster.fromNow(offset, dateObj=self.now))


CONFIG = Config()
SHARED = Shared()


def chaining(op, attr):
    def method(self, *args, **kwargs):
        op(self, attr, *args, **kwargs)
        return self

    return method


def append_to_attr(self, attr, *args):
    getattr(self, attr).extend([arg for arg in args if arg])


def prepend_to_attr(self, attr, *args):
    getattr(self, attr)[0:0] = list(args)


def update_attr(self, attr, **kwargs):
    getattr(self, attr).update(kwargs)


class Task:
    """
    A task definition, waiting to be created.

    Typical is to use chain the `with_*` methods to set or extend this object’s attributes,
    then call the `crate` or `find_or_create` method to schedule a task.

    This is an abstract class that needs to be specialized for different worker implementations.
    """

    def __init__(self, name: str):
        self.name = name
        self.description = ""
        self.scheduler_id = "taskcluster-github"
        self.provisioner_id = CONFIG.default_provisioner_id
        self.worker_type = "github-worker"
        self.deadline_in = "1 day"
        self.expires_in = "1 year"
        self.index_and_artifacts_expire_in = self.expires_in
        self.dependencies: List[str] = []
        self.scopes: List[str] = []
        self.routes: List[str] = []
        self.extra: Dict[str, Dict[str, str]] = {}
        self.priority: Optional[str] = None  # Defaults to 'lowest'
        self.artifacts: List[Tuple[str, str]] = []
        self.env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": os.environ["REPO_FULL_NAME"],
        }
        self.scripts: List[str] = []
        self.action_paths: Set[str] = set()
        self.gh_actions: collections.OrderedDict[
            str, gha.GithubAction
        ] = collections.OrderedDict()

    # All `with_*` methods return `self`, so multiple method calls can be chained.
    with_description = chaining(setattr, "description")
    with_scheduler_id = chaining(setattr, "scheduler_id")
    with_provisioner_id = chaining(setattr, "provisioner_id")
    with_worker_type = chaining(setattr, "worker_type")
    with_deadline_in = chaining(setattr, "deadline_in")
    with_expires_in = chaining(setattr, "expires_in")
    with_index_and_artifacts_expire_in = chaining(
        setattr, "index_and_artifacts_expire_in"
    )
    with_priority = chaining(setattr, "priority")

    with_dependencies = chaining(append_to_attr, "dependencies")
    with_scopes = chaining(append_to_attr, "scopes")
    with_routes = chaining(append_to_attr, "routes")

    with_extra = chaining(update_attr, "extra")
    with_env = chaining(update_attr, "env")

    def get_proxy_url(self) -> str:
        return os.environ["TASKCLUSTER_PROXY_URL"]

    def with_script(self, *script: str):
        self.scripts.extend(script)
        return self

    def with_early_script(self, *script: str):
        self.scripts[0:0] = list(script)
        return self

    def with_index_at(self, index_path: str):
        self.routes.append("index.%s.%s" % (CONFIG.index_prefix, index_path))
        return self

    def with_artifacts(self, *paths: str, type: str = "file"):
        """
        Add each path in `paths` as a task artifact
        that expires in `self.index_and_artifacts_expire_in`.

        `type` can be `"file"` or `"directory"`.

        Paths are relative to the task’s home directory.
        """
        for path in paths:
            if (type, path) in self.artifacts:
                raise ValueError("Duplicate artifact: " + path)  # pragma: no cover
            self.artifacts.append((type, path))
        return self

    def with_named_artifacts(self, name: str, path: str):
        raise NotImplementedError

    def build_worker_payload(self):  # pragma: no cover
        """
        Overridden by sub-classes to return a dictionary in a worker-specific format,
        which is used as the `payload` property in a task definition request
        passed to the Queue’s `createTask` API.

        <https://docs.taskcluster.net/docs/reference/platform/taskcluster-queue/references/api#createTask>
        """
        raise NotImplementedError

    def create(self) -> str:
        """
        Call the Queue’s `createTask` API to schedule a new task, and return its ID.

        <https://docs.taskcluster.net/docs/reference/platform/taskcluster-queue/references/api#createTask>
        """
        task_id = taskcluster.slugId()
        if self.gh_actions:
            self.gen_gha_payload(f"{task_id}.json")
        worker_payload = self.build_worker_payload()

        assert CONFIG.decision_task_id
        assert CONFIG.task_owner
        assert CONFIG.task_source

        def dedup(xs):
            seen = set()
            return [x for x in xs if not (x in seen or seen.add(x))]

        queue_payload = {
            "taskGroupId": CONFIG.decision_task_id,
            "dependencies": dedup([CONFIG.decision_task_id] + self.dependencies),
            "schedulerId": self.scheduler_id,
            "projectId": "divvun",
            "provisionerId": self.provisioner_id,
            "workerType": self.worker_type,
            "created": SHARED.from_now_json(""),
            "deadline": SHARED.from_now_json(self.deadline_in),
            "expires": SHARED.from_now_json(self.expires_in),
            "metadata": {
                "name": CONFIG.task_name_template % self.name,
                "description": self.description,
                "owner": CONFIG.task_owner,
                "source": CONFIG.task_source,
            },
            "payload": worker_payload,
        }
        scopes = self.scopes + CONFIG.scopes_for_all_subtasks
        routes = self.routes + CONFIG.routes_for_all_subtasks
        if any(r.startswith("index.") for r in routes):
            self.extra.setdefault("index", {})["expires"] = SHARED.from_now_json(
                self.index_and_artifacts_expire_in
            )
        dict_update_if_truthy(
            queue_payload,
            scopes=scopes,
            routes=routes,
            extra=self.extra,
            priority=self.priority,
        )

        SHARED.queue_service.createTask(task_id, queue_payload)
        print("Scheduled %s: %s" % (task_id, self.name))
        return task_id

    @staticmethod
    def find(index_path: str) -> str:
        full_index_path = "%s.%s" % (CONFIG.index_prefix, index_path)
        task_id = SHARED.index_service.findTask(full_index_path)["taskId"]
        print("Found task %s indexed at %s" % (task_id, full_index_path))
        return task_id

    def find_or_create(self, index_path: str) -> str:
        """
        Try to find a task in the Index and return its ID.

        The index path used is `{CONFIG.index_prefix}.{index_path}`.
        `index_path` defaults to `by-task-definition.{sha256}`
        with a hash of the worker payload and worker type.

        If no task is found in the index,
        it is created with a route to add it to the index at that same path if it succeeds.

        <https://docs.taskcluster.net/docs/reference/core/taskcluster-index/references/api#findTask>
        """
        task_id = SHARED.found_or_created_indexed_tasks.get(index_path)
        if task_id is not None:
            return task_id

        try:
            task_id = Task.find(index_path)
        except taskcluster.TaskclusterRestFailure as e:
            if e.status_code != 404:  # pragma: no cover
                raise
            if not CONFIG.index_read_only:
                self.with_index_at(index_path)
            task_id = self.create()

        SHARED.found_or_created_indexed_tasks[index_path] = task_id
        return task_id

    def with_additional_repo(self, repo_url: str, target: str):
        return self.with_script(
            """
            git clone --depth=1 %s %s
        """
            % (repo_url, target)
        )

    def with_curl_script(self, url: str, file_path: str):
        return self.with_script(
            """
            curl --compressed --ssl-no-revoke --retry 5 --connect-timeout 10 -Lf "%s" -o "%s"
        """
            % (url, file_path)
        )

    def with_curl_artifact_script(
        self,
        task_id: str,
        artifact_name: str,
        out_directory="",
        directory="public",
        rename=None,
        extract=False,
    ):
        queue_service = self.get_proxy_url() + "/api/queue"
        ret = self.with_dependencies(task_id).with_curl_script(
            queue_service
            + "/v1/task/%s/artifacts/%s/%s" % (task_id, directory, artifact_name),
            os.path.join(out_directory, rename or url_basename(artifact_name)),
        )
        if extract:
            ret = self.with_script(
                "tar xvf %s"
                % os.path.join(out_directory, rename or url_basename(artifact_name))
            )

        return ret

    def with_repo_bundle(self, name, dest, **kwargs):
        return self.with_curl_artifact_script(
            CONFIG.decision_task_id, f"{name}.bundle", "$HOME/tasks/$TASK_ID"
        ).with_repo(
            "$HOME/tasks/$TASK_ID/" + dest,
            f"$HOME/tasks/$TASK_ID/{name}.bundle",
            CONFIG.git_bundle_shallow_ref,
            "FETCH_HEAD",
            **kwargs,
        )

    def with_gha(self, name: str, gha: gha.GithubAction):
        if gha.git_fetch_url not in self.action_paths:
            self.with_additional_repo(gha.git_fetch_url, gha.repo_name)
            self.action_paths.add(gha.git_fetch_url)

        self.gh_actions[name] = gha
        return self

    def _gen_gha_payload(self, platform: str, payload_name: str):
        payload = {}

        for name, gha in self.gh_actions.items():
            script = gha.gen_script(platform)
            payload[name] = {
                "script": script,
                "mapping": gha.output_mapping(),
                "env": gha.env_variables(platform),
                "inputs": gha.args,
                "secret_inputs": gha.secret_inputs,
            }
        utils.create_extra_artifact(payload_name, json.dumps(payload).encode())

    def gen_gha_payload(self, name: str):
        raise NotImplementedError

    def with_prep_gha_tasks(self):
        raise NotImplementedError


class GenericWorkerTask(Task):
    """
    Task definition for a worker type that runs the `generic-worker` implementation.

    This is an abstract class that needs to be specialized for different operating systems.

    <https://github.com/taskcluster/generic-worker>
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_run_time_minutes = 30
        self.features: Dict[str, bool] = {}
        self.mounts: List[Dict[str, str]] = []

    with_max_run_time_minutes = chaining(setattr, "max_run_time_minutes")
    with_mounts = chaining(append_to_attr, "mounts")

    def build_command(self):  # pragma: no cover
        """
        Overridden by sub-classes to return the `command` property of the worker payload,
        in the format appropriate for the operating system.
        """
        raise NotImplementedError

    def build_worker_payload(self):
        """
        Return a `generic-worker` worker payload.

        <https://docs.taskcluster.net/docs/reference/workers/generic-worker/docs/payload>
        """
        worker_payload = {
            "command": self.build_command(),
            "maxRunTime": self.max_run_time_minutes * 60,
        }
        mounts = []
        seen = set()
        for m in self.mounts:
            if m["directory"] not in seen:
                mounts.append(m)
                seen.add(m["directory"])

        return dict_update_if_truthy(
            worker_payload,
            env=self.env,
            mounts=mounts,
            features=self.features,
            artifacts=[
                {
                    "type": type_,
                    "path": path,
                    "name": "public/" + url_basename(path),
                    "expires": SHARED.from_now_json(self.index_and_artifacts_expire_in),
                }
                for type_, path in self.artifacts
            ],
        )

    def with_features(self, *names: str):
        """
        Enable the given `generic-worker` features.

        <https://github.com/taskcluster/generic-worker/blob/master/native_windows.yml>
        """
        self.features.update({name: True for name in names})
        return self

    def _mount_content(self, url_or_artifact_name: str, task_id: str, sha256: str):
        if task_id:
            content = {"taskId": task_id, "artifact": url_or_artifact_name}
        else:
            content = {"url": url_or_artifact_name}
        if sha256:
            content["sha256"] = sha256
        return content

    def with_file_mount(
        self, url_or_artifact_name: str, task_id=None, sha256=None, path=None
    ):
        """
        Make `generic-worker` download a file before the task starts
        and make it available at `path` (which is relative to the task’s home directory).

        If `sha256` is provided, `generic-worker` will hash the downloaded file
        and check it against the provided signature.

        If `task_id` is provided, this task will depend on that task
        and `url_or_artifact_name` is the name of an artifact of that task.
        """
        return self.with_mounts(
            {
                "file": path or url_basename(url_or_artifact_name),
                "content": self._mount_content(url_or_artifact_name, task_id, sha256),
            }
        )

    def with_directory_mount(
        self, url_or_artifact_name: str, task_id=None, sha256=None, path=None
    ):
        """
        Make `generic-worker` download an archive before the task starts,
        and uncompress it at `path` (which is relative to the task’s home directory).

        `url_or_artifact_name` must end in one of `.rar`, `.tar.bz2`, `.tar.gz`, or `.zip`.
        The archive must be in the corresponding format.

        If `sha256` is provided, `generic-worker` will hash the downloaded archive
        and check it against the provided signature.

        If `task_id` is provided, this task will depend on that task
        and `url_or_artifact_name` is the name of an artifact of that task.
        """
        supported_formats = ["rar", "tar.bz2", "tar.gz", "zip"]
        for fmt in supported_formats:
            suffix = "." + fmt
            if url_or_artifact_name.endswith(suffix):
                return self.with_mounts(
                    {
                        "directory": path
                        or url_basename(url_or_artifact_name[: -len(suffix)]),
                        "content": self._mount_content(
                            url_or_artifact_name, task_id, sha256
                        ),
                        "format": fmt,
                    }
                )
        raise ValueError(
            "%r does not appear to be in one of the supported formats: %r"
            % (url_or_artifact_name, ", ".join(supported_formats))
        )  # pragma: no cover


class WindowsGenericWorkerTask(GenericWorkerTask):
    """
    Task definition for a `generic-worker` task running on Windows.

    Scripts are written as `.bat` files executed with `cmd.exe`.
    """

    def with_prep_gha_tasks(self):
        for gha in self.gh_actions.values():
            for out in gha.output_mappings:
                if out.task_id:
                    self.with_curl_artifact_script(
                        out.task_id,
                        "outputs.json",
                        "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\",
                        "private",
                        rename=out.task_id + ".json",
                    )
        return self.with_curl_artifact_script(
            CONFIG.decision_task_id,
            "%TASK_ID%.json",
            "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\",
            "private",
        ).with_script(
            "python -u %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\ci\\runner.py %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\%TASK_ID%.json"
        )

    def build_worker_payload(self):
        self.scopes.append("generic-worker:os-group:divvun/windows/Administrators")
        self.scopes.append("generic-worker:run-as-administrator:divvun/windows")
        self.with_features("runAsAdministrator")
        return dict_update_if_truthy(
            super().build_worker_payload(),
            osGroups=["Administrators"],
        )

    def build_command(self):
        return ['cmd.exe /C "{}"'.format(deindent("\n".join(self.scripts)))]

    def with_path_from_homedir(self, *paths: str):
        """
        Interpret each path in `paths` as relative to the task’s home directory,
        and add it to the `PATH` environment variable.
        """
        for p in paths:
            self.with_early_script(
                'set "PATH=%HOMEDRIVE%%HOMEPATH%\\{};%PATH%"'.format(p)
            )
            self.with_early_script(
                'set "PATH=%HOMEDRIVE%%HOMEPATH%\\{};%PATH%"'.format(p)
            )
        return self

    def with_repo(self, path, fetch_url, fetch_ref, checkout_sha, sparse_checkout=None):
        """
        Make a clone the git repository at the start of the task.
        This uses `CONFIG.git_url`, `CONFIG.git_ref`, and `CONFIG.git_sha`,
        and creates the clone in a `repo` directory in the task’s home directory.

        If `sparse_checkout` is given, it must be a list of path patterns
        to be used in `.git/info/sparse-checkout`.
        See <https://git-scm.com/docs/git-read-tree#_sparse_checkout>.
        """
        git = f"""
            git init {path}
            cd {path}
        """
        if sparse_checkout:
            self.with_mounts(
                {
                    "file": "sparse-checkout",
                    "content": {"raw": "\n".join(sparse_checkout)},
                }
            )
            git += """
                git config core.sparsecheckout true
                copy ..\\sparse-checkout .git\\info\\sparse-checkout
                type .git\\info\\sparse-checkout
            """
        git += """
            git fetch --verbose --no-tags {} {}
            git reset --hard {}
        """.format(
            assert_truthy(fetch_url),
            assert_truthy(fetch_ref),
            assert_truthy(checkout_sha),
        )
        return self.with_git().with_script(git)

    def with_repo_bundle(self, name: str, dest: str, **kwargs):
        return self.with_curl_artifact_script(
            CONFIG.decision_task_id,
            f"{name}.bundle",
            "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%",
        ).with_repo(
            "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\" + dest,
            f"%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\{name}.bundle",
            CONFIG.git_bundle_shallow_ref,
            "FETCH_HEAD",
            **kwargs,
        )

    def with_git(self):
        """
        Make the task download `git-for-windows` and make it available for `git` commands.

        This is implied by `with_repo`.
        """
        return (
            self.with_path_from_homedir("git\\cmd")
            .with_path_from_homedir("git\\bin")
            .with_path_from_homedir("git\\mingw64\\bin")
            .with_directory_mount(
                "https://github.com/git-for-windows/git/releases/download/v2.34.1.windows.1/Git-2.34.1-64-bit.tar.bz2",
                path="git",
            )
        )

    def with_curl_script(self, url, file_path):
        self.with_curl()
        return super().with_curl_script(url, file_path)

    def with_curl(self):
        return self.with_path_from_homedir(
            "curl\\curl-7.79.1-win64-mingw\\bin"
        ).with_directory_mount(
            "https://curl.se/windows/dl-7.79.1_4/curl-7.79.1_4-win64-mingw.zip",
            path="curl",
        )

    def with_rustup(self):
        """
        Download rustup.rs and make it available to task commands,
        but does not download any default toolchain.
        """
        return (
            self.with_path_from_homedir(".cargo\\bin")
            .with_early_script(
                "%HOMEDRIVE%%HOMEPATH%\\rustup-init.exe --default-toolchain none --profile=minimal -y"
            )
            .with_file_mount("https://win.rustup.rs/x86_64", path="rustup-init.exe")
        )

    def with_python3(self):
        """
        For Python 3, use `with_directory_mount` and the "embeddable zip file" distribution
        from python.org.
        You may need to remove `python37._pth` from the ZIP in order to work around
        <https://bugs.python.org/issue34841>.
        """
        return (
            self.with_curl_script(
                "https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe",
                "do-the-python.exe",
            )
            .with_script(
                "start /wait do-the-python.exe /quiet TargetDir=%HOMEDRIVE%%HOMEPATH%\\python3 InstallAllUsers=0 InstallLauncherAllUsers=0 /log C:\\log",
            )
            .with_path_from_homedir("python3", "python3\\Scripts")
        )

    def gen_gha_payload(self, name: str):
        return self._gen_gha_payload("win", name)


class UnixTaskMixin(Task):
    def with_repo(
        self, name, fetch_url, fetch_ref, checkout_sha, alternate_object_dir=""
    ):
        """
        Make a clone the git repository at the start of the task.
        This uses `CONFIG.git_url`, `CONFIG.git_ref`, and `CONFIG.git_sha`

        * generic-worker: creates the clone in a `repo` directory
          in the task’s directory.

        * docker-worker: creates the clone in a `/repo` directory
          at the root of the Docker container’s filesystem.
          `git` and `ca-certificate` need to be installed in the Docker image.

        """
        # Not using $GIT_ALTERNATE_OBJECT_DIRECTORIES since it causes
        # "object not found - no match for id" errors when Cargo fetches git dependencies
        return self.with_script(
            """
            git init {}
            cd {}
            echo "{alternate}" > .git/objects/info/alternates
            time git fetch --no-tags {} {}
            time git reset --hard {}
        """.format(
                name,
                name,
                assert_truthy(fetch_url),
                assert_truthy(fetch_ref),
                assert_truthy(checkout_sha),
                alternate=alternate_object_dir,
            )
        )


class MacOsGenericWorkerTask(UnixTaskMixin, GenericWorkerTask):
    """
    Task definition for a `generic-worker` task running on macOS.

    Scripts are interpreted with `bash`.
    """

    def get_proxy_url(self) -> str:
        """
        Mac workers don't run as root so the proxy can't listen on :80
        """
        return "http://taskcluster:8080"

    def build_command(self):
        # generic-worker accepts multiple commands, but unlike on Windows
        # the current directory and environment variables
        # are not preserved across commands on macOS.
        # So concatenate scripts and use a single `bash` command instead.
        return [
            [
                "/bin/bash",
                "--login",
                "-x",
                "-e",
                "-o",
                "pipefail",
                "-c",
                "{}".format(deindent("\n".join(self.scripts))),
            ]
        ]

    def with_python3(self):
        return self.with_early_script(
            """
            python3 -m ensurepip --user
            python3 -m pip install --user virtualenv
        """
        )

    def with_rustup(self):
        return self.with_early_script(
            """
            export PATH="$HOME/.cargo/bin:$PATH"
            which rustup || curl https://sh.rustup.rs -sSf | sh -s -- --default-toolchain none -y
            rustup self update
        """
        )

    def gen_gha_payload(self, name: str):
        return self._gen_gha_payload("macos", name)

    def with_prep_gha_tasks(self):
        for gha in self.gh_actions.values():
            for out in gha.output_mappings:
                if out.task_id:
                    self.with_curl_artifact_script(
                        out.task_id,
                        "outputs.json",
                        "$HOME/tasks/$TASK_ID/",
                        "private",
                        rename=out.task_id + ".json",
                    )
        return self.with_curl_artifact_script(
            CONFIG.decision_task_id,
            "$TASK_ID.json",
            f"/$HOME/tasks/$TASK_ID/",
            "private",
        ).with_script(
            "python3 -u $HOME/tasks/$TASK_ID/ci/runner.py /$HOME/tasks/$TASK_ID/$TASK_ID.json"
        )


class DockerWorkerTask(UnixTaskMixin, Task):
    """
    Task definition for a worker type that runs the `generic-worker` implementation.

    Scripts are interpreted with `bash`.

    <https://github.com/taskcluster/docker-worker>
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docker_image = "ubuntu:bionic-20180821"
        self.max_run_time_minutes = 30
        self.caches = {}
        self.features = {}
        self.capabilities = {}

    with_docker_image = chaining(setattr, "docker_image")
    with_max_run_time_minutes = chaining(setattr, "max_run_time_minutes")
    with_caches = chaining(update_attr, "caches")
    with_capabilities = chaining(update_attr, "capabilities")

    def with_prep_gha_tasks(self):
        for gha in self.gh_actions.values():
            for out in gha.output_mappings:
                if out.task_id:
                    self.with_curl_artifact_script(
                        out.task_id,
                        "outputs.json",
                        "$HOME/tasks/$TASK_ID/",
                        "private",
                        rename=out.task_id + ".json",
                    )
        return self.with_curl_artifact_script(
            CONFIG.decision_task_id,
            "$TASK_ID.json",
            f"/$HOME/tasks/$TASK_ID/",
            "private",
        ).with_script(
            "python3 -u $HOME/tasks/$TASK_ID/ci/runner.py /$HOME/tasks/$TASK_ID/$TASK_ID.json"
        )

    def build_worker_payload(self):
        """
        Return a `docker-worker` worker payload.

        <https://docs.taskcluster.net/docs/reference/workers/docker-worker/docs/payload>
        """
        worker_payload = {
            "image": self.docker_image,
            "maxRunTime": self.max_run_time_minutes * 60,
            "command": [
                "/bin/bash",
                "--login",
                "-x",
                "-e",
                "-o",
                "pipefail",
                "-c",
                "{}".format(deindent("\n".join(self.scripts))),
            ],
        }
        return dict_update_if_truthy(
            worker_payload,
            env=self.env,
            cache=self.caches,
            features=self.features,
            capabilities=self.capabilities,
            artifacts={
                "public/"
                + url_basename(path): {
                    "type": type_,
                    "path": path,
                    "expires": SHARED.from_now_json(self.index_and_artifacts_expire_in),
                }
                for (type_, path) in self.artifacts
            },
        )

    def with_features(self, *names: str):
        """
        Enable the given `docker-worker` features.

        <https://github.com/taskcluster/docker-worker/blob/master/docs/features.md>
        """
        self.features.update({name: True for name in names})
        return self

    def with_apt_update(self):
        return self.with_script(
            """
            apt update
        """
        )

    def with_apt_install(self, *pkgnames: str):
        return self.with_script(
            """
            DEBIAN_FRONTEND=noninteractive apt install -y %s
        """
            % " ".join(pkgnames)
        )

    def with_pip_install(self, *pkgnames: str):
        return self.with_script(
            """
            pip install %s
        """
            % " ".join(pkgnames)
        )

    def with_named_artifacts(self, name: str, path: str):
        assert "/" not in name
        targz = name + ".tar.gz"
        basedir = os.path.dirname(path)
        files = os.path.basename(path)
        return self.with_script(
            f"""
            find {basedir} -wholename "{files}" -exec tar --xform="s#{basedir}/##" -rvf /{targz} {{}} \\;
        """
        ).with_artifacts("/" + targz)

    def gen_gha_payload(self, name: str):
        return self._gen_gha_payload("linux", name)


def assert_truthy(x):
    assert x
    return x


def dict_update_if_truthy(d, **kwargs):
    for key, value in kwargs.items():
        if value:
            d[key] = value
    return d


def deindent(string: str) -> str:
    return re.sub("\n +", "\n ", string).strip()


def url_basename(url: str) -> str:
    return url.rpartition("/")[-1]


@contextlib.contextmanager
def make_repo_bundle(path: str, bundle_name: str, sha: str):
    cwd = os.getcwd()
    os.chdir(path)
    subprocess.check_call(["git", "config", "user.name", "Decision task"])
    subprocess.check_call(["git", "config", "user.email", "nobody@divvun.no"])
    tree = subprocess.check_output(["git", "show", sha, "--pretty=%T", "--no-patch"])
    message = "Shallow version of commit " + sha
    commit = subprocess.check_output(
        ["git", "commit-tree", tree.strip(), "-m", message]
    )
    subprocess.check_call(
        ["git", "update-ref", CONFIG.git_bundle_shallow_ref, commit.strip()]
    )
    subprocess.check_call(["git", "show-ref"])
    create = [
        "git",
        "bundle",
        "create",
        f"../{bundle_name}",
        CONFIG.git_bundle_shallow_ref,
    ]
    with subprocess.Popen(create) as p:
        os.chdir(cwd)
        yield
        exit_code = p.wait()
        if exit_code:
            sys.exit(exit_code)

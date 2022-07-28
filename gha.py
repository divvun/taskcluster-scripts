import requests
import yaml
import posixpath
import re
import os


class GithubAction:
    def __init__(self, path, args, *, run_if=None, npm_install=False, enable_post=True):
        """
        Path here is the github path to an actions which is {org}/{repo}/{action_path_in_repo}
        Args will all be put in the env as INPUT_{key} = {value}
        """
        # Path can be None from GithubActionScript
        if path and "@" in path:
            self.path, self.version = path.split("@", 1)
        else:
            self.path = path
            self.version = "master"
        self.args = {}
        self.post_path = None
        self.run_path = "index.js"
        self.parse_config()
        self.args.update(args)
        self.outputs_from = set()
        self.secret_inputs = {}
        self.condition = run_if
        self.env = {}
        self.cwd = None
        self.shell = None
        self.npm_install = npm_install
        self.enable_post = enable_post

    def env_variables(self, platform):
        env = {}

        if platform == "linux":
            env = {
                "RUNNER_TEMP": "$HOME/tasks/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/tasks/$TASK_ID",
                "GITHUB_REF": os.environ["GIT_REF"],
            }
        elif platform == "macos":
            env = {
                "RUNNER_TEMP": "$HOME/tasks/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/tasks/$TASK_ID",
                "GITHUB_REF": os.environ["GIT_REF"],
            }
        elif platform == "win":
            env = {
                "RUNNER_TEMP": "${HOME}/${TASK_ID}/_temp",
                "GITHUB_WORKSPACE": "${HOME}/${TASK_ID}",
                "GITHUB_REF": os.environ["GIT_REF"],
            }

        env.update(self.env)
        return env

    def parse_config(self):
        if not self.path:
            return

        url = (
            "https://raw.githubusercontent.com/"
            + self.repo_name
            + f"/{self.version}/"
            + self.action_path
            + "/action.yml"
        )
        config = requests.get(url).text
        config = yaml.full_load(config)
        for name, content in config.get("inputs", {}).items():
            if "default" in content:
                self.args[name] = content["default"]

        run_path = config.get("runs", {}).get("main")
        if run_path:
            self.run_path = run_path

        post_path = config.get("runs", {}).get("post")
        if post_path:
            self.post_path = post_path

    @property
    def repo_name(self):
        parts = self.path.split("/")
        assert len(parts) > 1

        return "/".join(parts[:2])

    @property
    def action_path(self):
        parts = self.path.split("/")

        return "/".join(parts[2:])

    @property
    def git_fetch_url(self):
        return f"https://github.com/{self.repo_name}"

    @property
    def script_path(self):
        return posixpath.join(self.action_path, self.run_path)

    @property
    def post_script_path(self):
        if not self.post_path or not self.enable_post:
            return None
        return posixpath.join(self.action_path, self.post_path)

    def task_root(self, platform):
        if platform == "linux":
            return "$HOME/tasks/$TASK_ID/_temp/"
        elif platform == "macos":
            return "$HOME/tasks/$TASK_ID/_temp/"
        elif platform == "win":
            return "${HOME}/${TASK_ID}/_temp/"
        else:
            raise NotImplementedError

    def gen_script(self, platform):
        task_root = self.task_root(platform)

        out = ""
        if self.npm_install:
            out += f"npm install {task_root}{self.repo_name}\n"
            self.env["NODE_PATH"] = f"{task_root}{self.repo_name}/node_modules"
        return out + f"node {task_root}{self.repo_name}/{self.script_path}"

    def gen_post_script(self, platform):
        task_root = self.task_root(platform)

        out = ""
        if self.npm_install:
            out += f"npm install {task_root}{self.repo_name}\n"
            self.env["NODE_PATH"] = f"{task_root}{self.repo_name}/node_modules"
        return out + f"node {task_root}{self.repo_name}/{self.post_script_path}"

    def with_outputs_from(self, task_id):
        self.outputs_from.add(task_id)
        return self

    def with_secret_input(self, input_name, secret, name):
        self.secret_inputs[input_name] = {"secret": secret, "name": name}

        # Remove the input from self.args in case it has a default
        if input_name in self.args:
            del self.args[input_name]
        return self

    def with_env(self, key, value):
        self.env[key] = value
        return self

    def with_cwd(self, cwd):
        self.cwd = cwd
        return self

    def with_shell(self, shell):
        self.shell = shell
        return self


class GithubActionScript(GithubAction):
    def __init__(self, script, *, run_if=None, post_script=None):
        super().__init__(None, {}, run_if=run_if)
        self.enable_post = post_script is not None
        self.script = script
        self.post_script = post_script

    def gen_script(self, _platform):
        return re.sub("\n +", "\n ", self.script).strip()

    def gen_post_script(self, _platform):
        return re.sub("\n +", "\n ", self.post_script).strip()

    @property
    def git_fetch_url(self):
        return None

    @property
    def post_script_path(self):
        return self.enable_post

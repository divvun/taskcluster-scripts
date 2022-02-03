import requests
import yaml
import posixpath
import re


class GithubAction:
    def __init__(self, path, args, *, run_if=None, npm_install=False):
        """
        Path here is the github path to an actions which is {org}/{repo}/{action_path_in_repo}
        Args will all be put in the env as INPUT_{key} = {value}
        """
        # Path can be None from GithubActionScript
        if path and '@' in path:
            self.path, self.version = path.split('@', 1)
        else:
            self.path = path
            self.version = 'master'
        self.args = {}
        self.run_path = "index.js"
        self.parse_config()
        self.args.update(args)
        self.outputs_from = set()
        self.secret_inputs = {}
        self.condition = run_if
        self.env = {}
        self.cwd = None
        self.npm_install = npm_install

    def env_variables(self, platform):
        env = {}

        if platform == "linux":
            env = {
                "RUNNER_TEMP": "$HOME/tasks/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/tasks/$TASK_ID",
            }
        elif platform == "macos":
            env = {
                "RUNNER_TEMP": "$HOME/tasks/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/tasks/$TASK_ID",
            }
        elif platform == "win":
            env = {
                "RUNNER_TEMP": "${HOME}/${TASK_ID}/_temp",
                "GITHUB_WORKSPACE": "${HOME}/${TASK_ID}",
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

    def gen_script(self, platform):
        if platform == "linux":
            task_root = "$HOME/tasks/$TASK_ID/_temp/"
        elif platform == "macos":
            task_root = "$HOME/tasks/$TASK_ID/_temp/"
        elif platform == "win":
            task_root = "${HOME}/${TASK_ID}/_temp/"
        else:
            raise NotImplementedError

        out = ""
        if self.npm_install:
            out += f"npm install {task_root}{self.repo_name}\n"
            self.env["NODE_PATH"] = f"{task_root}{self.repo_name}/node_modules"
        return out + f"node {task_root}{self.repo_name}/{self.script_path}"

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


class GithubActionScript(GithubAction):
    def __init__(self, script, *, run_if=None):
        super().__init__(None, {}, run_if=run_if)
        self.script = script

    def gen_script(self, _platform):
        return re.sub("\n +", "\n ", self.script).strip()

    @property
    def git_fetch_url(self):
        return None

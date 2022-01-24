import requests
import yaml
import posixpath


class GithubAction:
    def __init__(self, path, args, run_if=None):
        """
        Path here is the github path to an actions which is {org}/{repo}/{action_path_in_repo}
        Args will all be put in the env as INPUT_{key} = {value}
        """
        self.path = path
        self.args = {}
        self.run_path = "index.js"
        self.parse_config()
        self.args.update(args)
        self.outputs_from = set()
        self.secret_inputs = {}
        self.condition = run_if
        self.env = {}

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
                "RUNNER_TEMP": "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp",
                "GITHUB_WORKSPACE": "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\",
            }

        env.update(self.env)
        return env

    def parse_config(self):
        if not self.path:
            return

        url = (
            "https://raw.githubusercontent.com/"
            + self.repo_name
            + "/master/"
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

        if parts[0] == "actions":
            raise NotImplementedError

        return "/".join(parts[:2])

    @property
    def action_path(self):
        parts = self.path.split("/")
        if parts[0] == "actions":
            raise NotImplementedError

        return "/".join(parts[2:])

    @property
    def git_fetch_url(self):
        return f"https://github.com/{self.repo_name}"

    @property
    def script_path(self):
        return posixpath.join(self.action_path, self.run_path)

    def gen_script(self, _platform):
        return f"node {self.repo_name}/{self.script_path}"

    def with_outputs_from(self, task_id):
        self.outputs_from.add(task_id)
        return self

    def with_secret_input(self, input_name, secret, name):
        self.secret_inputs[input_name] = {"secret": secret, "name": name}

        # Remove the input from self.args in case it has a default
        del self.args[input_name]
        return self

    def with_env(self, key, value):
        self.env[key] = value
        return self


class GithubActionScript(GithubAction):
    def __init__(self, script, run_if=None):
        super().__init__(None, {}, run_if)
        self.script = script

    def gen_script(self, _platform):
        return self.script

    @property
    def git_fetch_url(self):
        return None


class ActionOutput:
    def __init__(self, action_name, output_name):
        self.action_name = action_name
        self.output_name = output_name
        self._value = None
        self._operator = None

    def eq(self, value):
        self._value = value
        self._operator = "eq"

    def to_dict(self):
        return {
            "action": self.action_name,
            "output": self.output_name,
            "operator": self._operator,
            "cmp": self._value,
        }

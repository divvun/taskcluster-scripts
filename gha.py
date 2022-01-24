import requests
import yaml
import posixpath


class OutputMapping:
    def __init__(
        self, input_name, mapped_output_action, mapped_output_name, from_task_id=None, as_env=False
    ):
        self.input_name = input_name
        self.mapped_output_action = mapped_output_action
        self.mapped_output_name = mapped_output_name
        self.task_id = from_task_id
        self.as_env = as_env

    def to_dict(self):
        mapping = {
            "input": self.input_name,
            "from": {
                "action": self.mapped_output_action,
                "output": self.mapped_output_name,
            },
            "task_id": self.task_id,
            "as_env": self.as_env,
        }

        return mapping


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
        self.output_mappings = []
        self.secret_inputs = {}
        self.condition = run_if
        self.env = {}

    def env_variables(self, platform):
        if platform == "linux":
            return {
                "RUNNER_TEMP": "$HOME/tasks/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/tasks/$TASK_ID",
            }

        if platform == "macos":
            return {
                "RUNNER_TEMP": "$HOME/tasks/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/tasks/$TASK_ID",
            }

        if platform == "win":
            return {
                "RUNNER_TEMP": "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp",
                "GITHUB_WORKSPACE": "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\",
            }

        raise NotImplementedError

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

        run_path = config.get('runs', {}).get('main')
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

    def output_mapping(self):
        return [output.to_dict() for output in self.output_mappings]

    def with_mapped_output(self, name, source_step, source_name, task_id=None, as_env=False):
        self.output_mappings.append(
            OutputMapping(name, source_step, source_name, task_id, as_env)
        )
        return self

    def with_secret_input(self, input_name, secret, name):
        self.secret_inputs[input_name] = {"secret": secret, "name": name}
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
        return { "action": self.action_name, "output": self.output_name, "operator": self._operator, "cmp": self._value }

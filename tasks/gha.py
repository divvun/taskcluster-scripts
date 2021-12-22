import requests
import yaml


class OutputMapping:
    def __init__(self, input_name, mapped_output_action, mapped_output_name, from_task_id=None):
        self.input_name = input_name
        self.mapped_output_action = mapped_output_action
        self.mapped_output_name = mapped_output_name
        self.task_id = from_task_id

    def to_dict(self):
        mapping = {
            "input": self.input_name,
            "from": {"action": self.mapped_output_action, "output": self.mapped_output_name},
            "task_id": self.task_id
        }

        return mapping


class GithubAction:
    def __init__(self, path, args):
        """
        Path here is the github path to an actions which is {org}/{repo}/{action_path_in_repo}
        Args will all be put in the env as INPUT_{key} = {value}
        """
        self.path = path
        self.args = {}
        self.parse_config()
        self.args.update(args)
        self.output_mappings = []
        self.secret_inputs = {}

    def env_variables(self, platform):
        if platform == 'linux':
            return {
                "RUNNER_TEMP": "$HOME/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/$TASK_ID",
            }
        elif platform == 'macos':
            return {
                "RUNNER_TEMP": "$HOME/$TASK_ID/_temp",
                "GITHUB_WORKSPACE": "$HOME/$TASK_ID",
            }
        elif platform == 'win':
            return {
                "RUNNER_TEMP": "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp",
                "GITHUB_WORKSPACE": "%HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\",
            }
        else:
            raise NotImplementedError


    def parse_config(self):
        url = 'https://raw.githubusercontent.com/' + self.repo_name + '/master/' + self.action_path + '/action.yml'
        config = requests.get(url).text
        config = yaml.full_load(config)
        for name, content in config.get('inputs', {}).items():
            if "default" in content:
                self.args[name] = content["default"]

    @property
    def repo_name(self):
        parts = self.path.split('/')
        assert len(parts) > 1

        if parts[0] == "actions":
            raise NotImplementedError
        else:
            return '/'.join(parts[:2])

    @property
    def action_path(self):
        parts = self.path.split('/')
        if parts[0] == "actions":
            raise NotImplementedError
        else:
            return '/'.join(parts[2:])

    @property
    def git_fetch_url(self):
        return f"https://github.com/{self.repo_name}"

    @property
    def script_path(self):
        return self.action_path + "/index.js"


    def gen_script(self, _platform):
        return "node {}/{}".format(self.repo_name, self.script_path)

    def output_mapping(self):
        return [output.to_dict() for output in self.output_mappings]


    def with_mapped_output(self, name, source_step, source_name, task_id=None):
        self.output_mappings.append(OutputMapping(name, source_step, source_name, task_id))
        return self

    def with_secret_input(self, input_name, secret, name):
        self.secret_inputs[input_name] = {"secret": secret, "name": name}
        return self

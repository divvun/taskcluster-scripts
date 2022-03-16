"""
This script interprets a .json file generated by the decision task to run a set
of github actions. To prevent accidental leaks, it will first gather all
secrets the current task has access to from taskcluster to be able to filter
them on its output. It will then iterate over the actions defined in that file
and execute them while handling all of the mapped inputs/outputs as well as a
few environment variables necessary for github actions to work.

As for github actions "commands", this supports:
    - ::add-mask (`core.setSecret`) to add a secret value to hide in the logs.
    - ::set-output (`core.setOutput`) to set an output value from this task.
      Note that all output values will be put in a outputs.json artifacts from
      the task and can be referenced from another task. This is useful to pass
      values across tasks running on different runners. Outputs are also stored
      in the runner and can be reused as inputs in subsequent actions.
    - ::add-path (`core.addPath`) to add a path to the `PATH` environment
      variable. This works on all 3 OSes and values will also be added to
      subsequent actions.

We also support extensions to the github actions commands:
    - ::create-artifact (`process.stdout.write('::create-artifact path=setup.exe::path/to/exe')`
      This will immediately create a public artifact attached to the task.

The JSON format should look like this:

    ```
    { "action_name": {..action_description..}}
    ```

    - Action name is used to map input/outputs, it can be anything
    - Action description is an object described below
    Note that actions are ran in order they're defined in in the object.

Action description format:
    ```
    {
        "env": {"name": "value", ...},
        "inputs": {"name": "value", ...},
        "secret_inputs": {"name": {"secret": "tc-secret", "name": "foo"}, ...},
        "outputs_from": ["task_id_1", ...],
        "script": "",
        "post_script": ""
    }
    ```
    - env: This should be dictionary containing environment variables to have
      while running the step. Note that this is action specific unlike the
      `::add-path` command.
    - inputs: static inputs to pass to the task. This will add
      `INPUT_{name.upper}` as an environment variable with the input value
      stringified. True/False will be stringified as "true"/"false".
    - secret_inputs: An object containing a name and a secret path description.
      Secrets in taskcluster are stored in a JSON object that you can get by
      name. That's what the `secret` key is for. Then we index that JSON with
      `name` and put the stringified value into `INPUT_{name.upper()}` just
      like a normal input.
    - outputs_from: A list of actions to get outputs from
    - script: The script to run. This is usually `node path/to/action.js` but could be anything.
    - post_script: Script to run unconditionally after the task
"""

import sys
import asyncio
import codecs
import json
import os
import platform
import subprocess
import shutil
import tempfile
import time

from collections import defaultdict
from typing import Set, Dict, List, Any
from taskcluster import helper

import utils

SECRETS: Set[str] = set()
OUTPUTS: defaultdict[str, Dict[str, str]] = defaultdict(lambda: {})
EXTRA_PATH: List[str] = []
CURRENT_STATUS = None
_ORIG_PRINT = print


def filtered_print(*args):
    """
    This function is designed to replace the original print function to avoid
    accidental secret leaks. It'll replace all secrets contained in the
    `SECRETS` global variable with `[*******]`.
    """
    filtered = []
    for arg in args:
        for secret in SECRETS:
            arg = str(arg).replace(secret, "[******]")
        filtered.append(arg)
    try:
        _ORIG_PRINT(*filtered)
    except UnicodeEncodeError:
        _ORIG_PRINT("[Unicode decode error]")


print = filtered_print


def gather_secrets():
    """
    Gather all available secrets from taskcluster and put them into the global
    `SECRETS` variable. This should be called quite early to avoid accidental
    secrets leaking.
    """
    secrets_service = helper.TaskclusterConfig().get_service("secrets")
    secret_names: Set[str] = set()

    def get_values_from_json(obj: Any) -> Set[str]:
        """
        Returns a list of values contained in a JSON object by recursively traversing it.
        """
        out = set()

        def flatten(x):
            if isinstance(x, dict):
                for value in x.values():
                    flatten(value)
            elif isinstance(x, list):
                for value in x:
                    flatten(value)
            else:
                out.add(x)

        flatten(obj)
        return out

    continuation = None
    while True:
        res = secrets_service.list(continuationToken=continuation)
        secret_names.update(set(res["secrets"]))
        if not res.get("continuationToken"):
            break
        continuation = res["continuationToken"]

    for name in secret_names:
        try:
            res = secrets_service.get(name)
            SECRETS.update(get_values_from_json(res["secret"]))
        except:
            # This happens when we're not allowed to read the secret. Unfortunately
            # there's no way of filtering out secrets we can't read from the
            # listing so we have to try to get them all.
            pass


async def process_command(step_name: str, line: str):
    """
    Try processing a command from a github action.
    Return True to keep the line in the logs, False to hide it
    """

    if line.startswith("::add-mask::"):
        secret = line[len("::add-mask::") :].lstrip().strip()
        if not secret:
            return

        SECRETS.add(secret)
        return

    print(line)

    if line.startswith("::set-output"):
        output = line[len("::set-output") :]
        name, value = output.split("::", 1)
        name = name.split("=")[1]
        OUTPUTS[step_name][name] = value
    elif line.startswith("::add-path::"):
        path = line[len("::add-path::") :]
        EXTRA_PATH.append(path)
    elif line.startswith("::set-cwd::"):
        path = line[len("::set-cwd::") :]
        os.chdir(os.path.expandvars(path))
    elif line.startswith("::set-env"):
        output = line[len("::set-env") :]
        name, value = output.split("::", 1)
        name = name.split("=")[1]
        os.environ[name] = value.strip().lstrip()
    elif line.startswith("::create-artifact"):
        output = line[len("::create-artifact") :]
        name, path = output.split("::", 1)
        name = name.split("=")[1]
        with open(path, "rb") as fd:
            await utils.create_extra_artifact_async(name, fd.read(), public=True)

    return


async def process_line(step_name: str, line: str):
    """
    Process a line from the task logs. This will check if it's a command or
    not, process that and then print the line on stdout. Note that since we've
    overridden the print command, secrets are filtered out
    """
    if line.startswith("::"):
        await process_command(step_name, line)
        return None

    print(line)


def get_env_for(step_name: str, step: Dict[str, Any]):
    """
    Return the environment for an action by combining the current environment
    (to forward taskcluster infos) and the `env`, `inputs`, `secret_inputs` and
    `mapping` fields from the description as well a few extra things either
    needed by our builders to behave properly or by github actions.
    """

    def to_string(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)

        return value

    env = os.environ
    secrets_service = helper.TaskclusterConfig().get_service("secrets")
    all_outputs = OUTPUTS
    for output in step["outputs_from"]:
        with open(os.path.join(os.environ["GITHUB_WORKSPACE"], output + ".json")) as fd:
            values = json.loads(fd.read())
        all_outputs.update(values)

    for name, value in step["env"].items():
        env[name] = parse_value_from(os.path.expandvars(to_string(value)), all_outputs)
        os.environ = env

    for name, value in step["inputs"].items():
        env["INPUT_" + name.upper()] = parse_value_from(
            os.path.expandvars(to_string(value)), all_outputs
        )
        os.environ = env

    for input_name, secret in step["secret_inputs"].items():
        name = "INPUT_" + input_name.upper()
        res = secrets_service.get(secret["secret"])["secret"]
        parts = secret["name"].split(".")
        for part in parts:
            res = res[part]
        env[name] = to_string(res)

    env["GITHUB_ACTION"] = step_name
    if platform.system() == "Darwin":
        # Macos builders don't run as root so the proxy listens on :8080 instead of :80
        env["TASKCLUSTER_PROXY_URL"] = "http://taskcluster:8080"
        env["PATH"] = env["PATH"] + ":/opt/homebrew/bin"
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"
    else:
        env["TASKCLUSTER_PROXY_URL"] = "http://taskcluster"
    env["BUILD_DIR"] = env["GITHUB_WORKSPACE"]
    env["RUNNER_WORKSPACE"] = env["GITHUB_WORKSPACE"]
    env["RUNNER_TOOL_CACHE"] = os.path.join(env["RUNNER_TEMP"], "_tc")
    env["GITHUB_ENV"] = os.path.expandvars(os.path.join(env["RUNNER_TEMP"], "GITHUB_PATH"))
    # We can't acces the real github run id, this is the closest we'll get to an unique monotically incrementing number
    # Take milliseconds so we can start hight than the current github run id at the time of writing
    env["GITHUB_RUN_NUMBER"] = str(int(time.time() * 1000))

    if os.path.isfile(env["GITHUB_ENV"]):
        with open(env["GITHUB_ENV"], "r") as fd:
            for line in fd.readlines():
                try:
                    name, value = line.split('=', 1)
                    env[name] = value.strip()
                except:
                    pass
    else:
        os.makedirs(os.path.dirname(env["GITHUB_ENV"]), exist_ok=True)
        open(env["GITHUB_ENV"], "w").close()

    if EXTRA_PATH:
        if platform.system() == "Windows":
            env["PATH"] = env["PATH"] + ";" + ";".join(EXTRA_PATH)
        else:
            env["PATH"] = env["PATH"] + ":" + ":".join(EXTRA_PATH)

    return env


def write_outputs():
    """
    Write the outputs from all actions that ran in our task. Those might be
    needed by other tasks. Note that those are private artifacts in case
    secrets creep up in them
    """
    utils.create_extra_artifact("outputs.json", json.dumps(OUTPUTS).encode())


async def run_action(action_name: str, action: Dict[str, Any], post=False):
    script_index = "post_script" if post else "script"
    print(f"Running {action_name}")
    env = get_env_for(action_name, action)

    extra_args = {}

    cwd = action.get('cwd')
    if platform.system() == "Windows":
        shell = action.get("shell", "pwsh")
        if shell == "cmd":
            tmp = tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False);
            tmp.write(action[script_index])
            cmdargs = ["cmd", "/C", "call " + tmp.name]
            print("Writing", action[script_index], " to", tmp.name)
            # Force close the file here because cmd is dumb and doesn't want to run if the file is still opened
            tmp.close()
        else:
            cmdargs = ["pwsh", "-c", action[script_index]]

        print("Running ", cmdargs)

        process = await asyncio.subprocess.create_subprocess_exec(
            *cmdargs,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            limit=1024*256,
            **extra_args,
        )
    else:
        print("Running: ", action[script_index])
        if platform.system() == "Linux":
            # Ubuntu uses dash as its /bin/sh which breaks env variables with dashes in them
            extra_args["executable"] = "/bin/bash"
        process = await asyncio.subprocess.create_subprocess_shell(
            action[script_index],
            env=env,
            cwd=cwd,
            limit=1024*256,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **extra_args,
        )

    assert process.stdout

    decoder = codecs.getincrementaldecoder(sys.stdout.encoding)(errors="replace")
    while True:
        line = await process.stdout.readline()
        if not line:
            break

        line_str = decoder.decode(line).strip().lstrip()
        await process_line(action_name, line_str)

    await process.wait()

    if process.returncode != 0:
        print(f"Process exited with code: {process.returncode}")
        print(await process.stdout.read())
        raise SystemError()


def should_run(condition, step):
    all_outputs = OUTPUTS
    for output in step["outputs_from"]:
        with open(os.path.join(os.environ["GITHUB_WORKSPACE"], output + ".json")) as fd:
            values = json.loads(fd.read())
        all_outputs.update(values)
    return parse_value_from(condition, all_outputs) == "true"


def parse_value_from(s, outputs):
    remainder = s
    out = ""

    while remainder:
        start_index = remainder.find("${{")
        if start_index == -1:
            out += remainder
            return out

        end_index = remainder.find("}}")
        if end_index == -1:
            raise ValueError(f"Parse error on variable in {remainder}")

        out += remainder[:start_index]
        variable = remainder[start_index + 3 : end_index].strip().lstrip()
        parts = variable.split()
        # ${{ steps.step_name.outputs.foo }} or ${{ steps.step_name.outputs['foo'] }}
        if len(parts) == 1:
            if parts[0].strip().lstrip() == "job.status":
                if CURRENT_STATUS is None:
                    return "${{ job.status }}"
                return CURRENT_STATUS

            var_name = parts[0].split(".")
            if var_name[0] != "steps":
                raise ValueError(f"Unsupported operation in {remainder}")

            if len(var_name) == 3:
                # ${{ steps.step_name.outputs['foo'] }}
                value_name_start_index = var_name[2].find("['")
                value_name_end_index = var_name[2].find("']")
                if value_name_start_index == -1 or value_name_end_index == -1:
                    raise ValueError(f"Error while parsing variable in {remainder}")
                output_name = var_name[2][
                    value_name_start_index + 2 : value_name_end_index
                ]
                step_name = var_name[1]
            elif len(var_name) == 4:
                # ${{ steps.step_name.outputs.foo }}
                if var_name[2] != "outputs":
                    raise ValueError(
                        f"Unsupported operation {var_name[2]} in {remainder}"
                    )

                step_name, output_name = var_name[1], var_name[3]
                if step_name not in outputs:
                    return "undefined"
                if output_name not in outputs[step_name]:
                    return "undefined"
            else:
                raise ValueError(f"Error while parsing variable in {remainder}")

            out += outputs[step_name][output_name]
        else:
            if out:
                raise ValueError("Conditions can't be concatenated")
            return parse_condition(variable, outputs, 0)

        remainder = remainder[end_index + 2 :]
    return out


def parse_condition(condition, outputs, depth):
    condition = condition.strip().lstrip()

    parens_start = condition.find("(")
    if parens_start != -1:
        parens_depth = 1
        parens_end = None
        # Find matching parens
        for index, c in enumerate(condition[parens_start + 1 :]):
            if c == "(":
                parens_depth += 1
            if c == ")":
                parens_depth -= 1
                if parens_depth == 0:
                    parens_end = index + parens_start
                    break
        if not parens_end:
            raise ValueError(f"Syntax error in {condition}, missing `)`")

        inner = parse_condition(
            condition[parens_start + 1 : parens_end + 1], outputs, depth + 1
        )

        condition = condition[:parens_start] + str(inner) + condition[parens_end + 2 :]
        return parse_condition(condition, outputs, depth + 1)

    def to_py(value):
        if value == "false":
            return False
        if value == "true":
            return True
        if value == "undefined":
            return None
        return value

    def eq(left, right):
        left = to_py(left)
        right = to_py(right)
        return str(left == right).lower()

    def neq(left, right):
        left = to_py(left)
        right = to_py(right)
        return str(left != right).lower()

    def and_(left, right):
        left = to_py(left)
        right = to_py(right)
        return str(left and right).lower()

    def or_(left, right):
        left = to_py(left)
        right = to_py(right)
        return str(left or right).lower()

    ops = {
        "&&": and_,
        "||": or_,
        "==": eq,
        "!=": neq,
    }

    for op, func in ops.items():
        op_start = condition.find(op)
        if op_start != -1:
            left_start = 0
            for idx, c in enumerate(reversed(condition[:op_start])):
                # Search for the previous operator
                if c in ("&", "|", "(", ")"):
                    left_start = op_start - idx
                    break

            right_end = len(condition)
            for idx, c in enumerate(condition[op_start + len(op) :]):
                # Search for the next operator
                if c in ("&", "|", "(", ")"):
                    right_end = op_start + idx
                    break

            left = parse_condition(condition[left_start:op_start], outputs, depth + 1)
            right = parse_condition(
                condition[op_start + len(op) : right_end], outputs, depth + 1
            )
            inner = func(left, right)
            condition = condition[:left_start] + str(inner) + condition[right_end:]
            return parse_condition(condition, outputs, depth + 1)

    if condition in ("null", "true", "false", "undefined"):
        return condition

    if condition.startswith('"') and condition.endswith('"'):
        return condition[1:-1]

    if condition.startswith("'") and condition.endswith("'"):
        return condition[1:-1]

    if not condition:
        raise ValueError("Parsing error")
    # If we end up here, we are out of normal types, it's a variable that comes fromn outputs
    return parse_value_from("${{ " + condition + " }}", outputs)


async def main():
    gather_secrets()
    file = sys.argv[1]
    with open(file) as fd:
        actions = json.loads(fd.read())

    # Set HOME on windows. Since the script is ran from CMD, $HOME doesn't
    # exist yet but since we need to share variables with powershell, we need
    # it to be there.
    if "HOME" not in os.environ:
        os.environ["HOME"] = os.path.expandvars("%HOMEDRIVE%%HOMEPATH%")

    post_actions = []
    try:
        for name, action in actions.items():
            if "condition" in action:
                if not should_run(action["condition"], action):
                    print("Ignoring {} because condition was false".format(name))
                    continue
            await run_action(name, action)
            if "post_script" in action and action["post_script"]:
                post_actions.append((name, action))
        CURRENT_STATUS = "success"
    except Exception as e:
        print(e)
        CURRENT_STATUS = "failed"
        raise
    finally:
        for (name, action) in post_actions:
            await run_action(name, action, post=True)



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)
        raise
    finally:
        # Cleanup on macos since it's the only runner not entirely stateless.
        if platform.system() == "Darwin":
            shutil.rmtree(os.environ["GITHUB_WORKSPACE"])

    write_outputs()

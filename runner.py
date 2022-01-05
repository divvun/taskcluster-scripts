from collections import defaultdict
import sys
import asyncio
from taskcluster import helper
import codecs
import json
import os
import platform
import subprocess
import decisionlib
import shutil

SECRETS = set()
OUTPUTS = defaultdict(lambda: {})
EXTRA_PATH = []
_ORIG_PRINT = print

def filtered_print(*args):
    filtered = []
    for arg in args:
        for secret in SECRETS:
            arg = str(arg).replace(secret, "[******]")
        filtered.append(arg)
    _ORIG_PRINT(*filtered)

print = filtered_print

def gather_secrets():
    secrets_service = helper.TaskclusterConfig().get_service("secrets")
    secret_names = set()

    def get_values_from_json(obj):
        out = set()

        def flatten(x):
            if type(x) is dict:
                for value in x.values():
                    flatten(value)
            elif type(x) is list:
                for a in x:
                    flatten(a)
            else:
                out.add(x)

        flatten(obj)
        return out

    continuation = None
    while True:
        res = secrets_service.list(continuationToken=continuation)
        secret_names.update(set(res['secrets']))
        if not res.get('continuationToken'):
            break
        continuation = res['continuationToken']

    for name in secret_names:
        try:
            res = secrets_service.get(name)
            SECRETS.update(get_values_from_json(res['secret']))
        except:
            # This happens when we're not allowed to read the secret. Unfortunately
            # there's no way of filtering out secrets we can't read from the
            # listing so we have to try to get them all.
            pass


async def process_command(step_name, line):
    if line.startswith('::add-mask::'):
        secret = line[len('::add-mask::'):]
        SECRETS.add(secret)
    elif line.startswith('::set-output'):
        output = line[len('::set-output'):]
        name, value = output.split('::', 1)
        name = name.split('=')[1]
        OUTPUTS[step_name][name] = value
    elif line.startswith('::add-path::'):
        secret = line[len('::add-path::'):]
        EXTRA_PATH.append(secret)
    elif line.startswith('::create-artifact'):
        output = line[len('::create-artifact'):]
        name, path = output.split('::', 1)
        name = name.split('=')[1]
        with open(path, 'rb') as fd:
            await decisionlib.create_extra_artifact_async(name, fd.read(), public=True)

    return True


async def process_line(step_name: str, line: str):
    if line.startswith('::'):
        if not await process_command(step_name, line):
            return None


    for secret in SECRETS:
        line = line.replace(secret, "[******]")

    print(line)


def get_env_for(step_name, step):
    def to_string(value):
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return value

    env = os.environ
    secrets_service = helper.TaskclusterConfig().get_service("secrets")
    for name, value in step["env"].items():
        env[name] = os.path.expandvars(value)
        os.environ = env

    for name, value in step["inputs"].items():
        env["INPUT_" + name.upper()] = os.path.expandvars(to_string(value))
        os.environ = env

    for input_name, secret in step["secret_inputs"].items():
        name = "INPUT_" + input_name.upper()
        res = secrets_service.get(secret['secret'])['secret'][secret['name']]
        env[name] = to_string(res)

    for mapping in step['mapping']:
        name = "INPUT_" + mapping['input'].upper()
        if mapping['task_id']:
            with open(os.path.join(os.environ["GITHUB_WORKSPACE"], mapping['task_id'] + '.json')) as fd:
                values = json.loads(fd.read())
            print(values)
            env[name] = values[mapping['from']['action']][mapping['from']['output']]
        else:
            env[name] = OUTPUTS[mapping['from']['action']][mapping['from']['output']]

    env["GITHUB_ACTION"] = step_name
    if platform.system() == 'Darwin':
        env["TASKCLUSTER_PROXY_URL"] = "http://taskcluster:8080"
        env["PATH"] = env["PATH"] + ":/opt/homebrew/bin"
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"
    else:
        env["TASKCLUSTER_PROXY_URL"] = "http://taskcluster"

    if EXTRA_PATH:
        if platform.system() == 'Windows':
            env["PATH"] = env["PATH"] + ';' + ";".join(EXTRA_PATH)
        else:
            env["PATH"] = env["PATH"] + ':' + ":".join(EXTRA_PATH)

    return env


def write_outputs():
    decisionlib.create_extra_artifact("outputs.json", json.dumps(OUTPUTS).encode())


async def run_step(step_name, step):
    env = get_env_for(step_name, step)

    process = await asyncio.subprocess.create_subprocess_shell(step["script"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,)
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    while True:
        line = await process.stdout.readline()
        if not line:
            break

        line = decoder.decode(line).strip().lstrip()
        await process_line(step_name, line)

    await process.wait()

    if process.returncode != 0:
        print(f"Process exited with code: {process.returncode}")
        raise SystemError()


async def main():
    gather_secrets()
    file = sys.argv[1]
    with open(file) as fd:
        tasks = json.loads(fd.read())

    for name, step in tasks.items():
        await run_step(name, step)


try:
    asyncio.run(main())
finally:
    pass
    # Cleanup on macos
    #if platform.system() == 'Darwin':
    #shutil.rmtree(os.environ['GITHUB_WORKSPACE'])

write_outputs()

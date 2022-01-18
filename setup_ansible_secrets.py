import json
import os
import sys
import urllib.request

proxy_url = os.environ['TASKCLUSTER_PROXY_URL'].rstrip('/')
secret_url = proxy_url + '/api/secrets/v1/secret/%s' % sys.argv[1]

with urllib.request.urlopen(secret_url) as response:
    if response.status != 200:
        raise RuntimeError('non-200 response from ' + secret_url)
    secret = json.load(response)


os.makedirs("./tmp")
with open("tmp/id_ed25519", "w") as fd:
    fd.write(secret['secret']['SSH_PRIVATE_KEY'])

with open("tmp/id_ed25519.pub", "w") as fd:
    fd.write(secret['secret']['SSH_PUBLIC_KEY'])

with open("tmp/vars.yml", "w") as fd:
    fd.write(json.dumps(secret['secret']))

print('export HOST=%s' % secret['secret']['HOST'])

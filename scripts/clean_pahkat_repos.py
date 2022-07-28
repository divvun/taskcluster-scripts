import toml
import os.path
import boto3.session
from botocore.config import Config
import os
import urllib.parse

session = boto3.session.Session()
config = Config(
   retries = {
      'max_attempts': 10000,
      'mode': 'legacy'
   }
)

REGION = os.environ["S3_REGION"]
ENDPOINT = os.environ["S3_ENDPOINT"]
ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
SECRET_KEY = os.environ["S3_SECRET_KEY"]

client = session.client('s3',
                        region_name=REGION,
                        endpoint_url=ENDPOINT,
                        aws_access_key_id=ACCESS_KEY,
                        config=config,
                        aws_secret_access_key=SECRET_KEY)

packages_in_index = set()
exceptions = { "/artifacts/giellakbd-android-jnilibs.zip" }

for root, _, files in os.walk('.'):
    # Ignore .git
    if root.startswith('./.'):
        continue
    for f in files:
        if f.endswith('.toml'):
            parsed = toml.load(os.path.join(root, f))
            # Ignore packages without any release
            if 'release' not in parsed:
                continue

            for release in parsed['release']:
                for target in release['target']:
                    url = target['payload']['url']
                    filename = urllib.parse.urlparse(url).path
                    packages_in_index.add(filename)

packages_in_bucket = set()
for object_path in client.list_objects_v2(Bucket="divvun", Prefix="pahkat/artifacts/")['Contents']:
    # Ignore directory objects
    if object_path['Size'] == 0:
        continue
    packages_in_bucket.add("/" + object_path["Key"].split('/', 1)[1])

packages_to_remove = packages_in_bucket - packages_in_index - exceptions
for package in packages_to_remove:
    path = "pahkat/" + package[1:]
    print(path)
    #client.delete_object(Bucket='divvun', Key=path)

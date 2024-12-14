import asyncio
import os
import taskcluster
from taskcluster import helper
from taskcluster.aio import upload


async def create_extra_artifact_async(path: str, content: bytes, public=False):
    """
    Function used to create extra artifacts that were not defined in the task
    description. This is useful for conditional artifacts and used for the
    `::create-artifact` command and the outputs.json file we use to pass
    outputs across tasks. If you need a sync version, call `create_extra_artifact`.
    """
    if public:
        path = "public/" + path
    else:
        path = "private/" + path

    queue = helper.TaskclusterConfig().get_service("queue")

    ret = queue.createArtifact(
        os.environ["TASK_ID"],
        os.environ["RUN_ID"],
        path,
        {
            "contentType": "plain/text",
            "expires": taskcluster.fromNow("1 day"),
            "storageType": "object",
        },
    )

    object_service = helper.TaskclusterConfig().get_service("object")

    retries = 0

    while True:
        try:
            await upload.uploadFromBuf(
                projectId=ret["projectId"],
                name=ret["name"],
                contentType="plain/text",
                contentLength=len(content),
                expires=ret["expires"],
                data=content,
                objectService=object_service,
                uploadId=ret["uploadId"],
            )
            break
        except:
            if retries >= 3:
                raise
            retries += 1

    queue.finishArtifact(
        os.environ["TASK_ID"], os.environ["RUN_ID"], path, {"uploadId": ret["uploadId"]}
    )


def create_extra_artifact(path: str, content: bytes, public=False):
    """
    Sync version of `create_extra_artifact_async` in case you're not in an
    async context. Do not call this function while in an event loop, it'll
    raise an exception
    """
    coro = create_extra_artifact_async(path, content, public)
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)
    loop.close()
    return result


def secrets():
    client = taskcluster.Secrets({
        "rootUrl": os.environ["TASKCLUSTER_PROXY_URL"] 
    })
    secrets = client.get("divvun")
    loadedSecrets = secrets["secret"]
    return loadedSecrets

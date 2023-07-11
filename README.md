# Introduction

As far as CI is concerned, this repo is where it all starts. For both Divvun and Giellalt.

When a build is triggered, `decision_task.py` is responsible for deciding what to do with the action and running the appropriate build actions. In many cases, this repo uses the [taskcluster-gha](https://github.com/divvun/taskcluster-gha) repo to perform GitHub Actions for actually doing the build/check/release. It's therefore helpful when working on the CI to have both repos checked out because the code that needs editing may be in either, or both.

# Building

Unlike `taskcluster-gha`, no building is necessary. Just edit the necessary `.py` file and push, then trigger a build to see the results.

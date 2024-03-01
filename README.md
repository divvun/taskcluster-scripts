# Introduction

As far as CI is concerned, this repo is where it all starts. For both Divvun and Giellalt.

When a build is triggered, `decision_task.py` is responsible for deciding what to do and runs the appropriate build actions. This repo makes heavy use of the [taskcluster-gha](https://github.com/divvun/taskcluster-gha) repo to perform GitHub Actions for actually doing the build/check/release. It's therefore helpful when working on the CI to have both repos checked out because the code that needs editing may be in either, or both.

# Building

Unlike `taskcluster-gha`, no building is necessary. Just edit the necessary `.py` file and push, then trigger a build to see the results.

# Development

Let's say you need to make changes to the CI/CD. This is usually a commit-heavy process that is sure to result in many failed builds before your eureka moment. Therefore it's best to make your mess on a branch to prevent *all* builds from failing and to keep `main` clean. Later, you can squash and merge via pull request once it's cleaned up and working.

This is the workflow:

### 1. Set up a branch for `taskcluster-scripts`

1. Identify a repo that can be used for testing. If making changes to spellers, for example, you might use [`lang-fit`](https://github.com/giellalt/lang-fit). If working on keyboards, maybe you'll use [`keyboard-fit`](https://github.com/giellalt/keyboard-fit/). These repos have been used in the past, but check with the powers that be to find a repo that's suitable for the changes you'll make.
2. Clone this here repo (`taskcluster-scripts`) and create your new branch.
3. Add a log statement so you'll be able to confirm you branch is working, [something like this](https://github.com/divvun/taskcluster-scripts/pull/8/commits/9eb8571b3d8b8db4aa354960c17bbe36be82b436). Push it to origin.
4. Edit the `.taskcluster.yml` file in your test repo from step 1 to use your new branch, using the `CI_REPO_REF` variable. It will look [something like this](https://github.com/giellalt/lang-fit/commit/cbcc6e6f34a063096f54f4ea56916818953a93e3). Push the change (make sure the branch you made in the previous step is also pushed). This will trigger CI.
5. You're now using your testing branch for `taskcluster-scripts` 🎉. You can [check taskcluster](https://divvun-tc.giellalt.org) to make sure nothing broke and your log statement from step 3 shows up before moving on to the next step.

### 2. Set up a branch for `taskcluster-gha`

In 97% of cases, you'll also need to make changes to the `taskcluster-gha` repo. These are the GitHub Actions used by this repo that do most of the work.

Steps:

1. Clone the [`taskcluster-gha`](https://github.com/divvun/taskcluster-gha) repo.
2. Create a branch for your changes. It might be wise to use the same branch name you used in `taskcluster-scripts`.
3. Add a log statement to one of the Github actions so you'll be able to confirm your branch is being used. Something like `core.debug("HELLO FROM THE <YOUR-BRANCH-HERE> BRANCH!!!")`. [Something like this](https://github.com/divvun/taskcluster-gha/commit/8885cc9e7ba3aa1c8e9230c62a7e4e7273cd5dc4).
4. [Build](https://github.com/divvun/taskcluster-gha?tab=readme-ov-file#building) and push your branch.

### 3. Point `taskcluster-scripts` at your `taskcluster-gha` branch.

Now find the place where you call the `taskcluster-gha` you edited in the previous step, and set it to use your branch. In the [example above in step 3](https://github.com/divvun/taskcluster-gha/commit/8885cc9e7ba3aa1c8e9230c62a7e4e7273cd5dc4), we edited the `lang/check/` action.

Calling the `lang/check` action using a branch looks like this:

```python
# taskcluster-scripts/tasks/lang_task.py
...
.with_gha(
    "check_analysers",
    GithubAction(
        "divvun/taskcluster-gha/lang/check", {},
        branch="<YOUR-BRANCH-HERE>"
    )
)
...
```
Note: all other actions are unnaffected; they will use the `main` branch. If you want to use your branch for multiple actions, you'll specify the branch for each of them as shown above. You can use multiple branches if you like. More info on the [pull request for this feature](https://github.com/divvun/taskcluster-scripts/pull/9).

To test:

1. Make a change similar to the one shown above to call your `taskcluster-gha` branch.
2. Commit and push.
3. Trigger CI to see that your print statement is appearing in the logs. You can trigger CI by pushing a change to your `lang-` or `keyboard-` etc repo.

You'll be doing this a lot. This one-liner makes it easy:
```bash
# ~/Projects/ttc/divvun/lang-fit
git pull && git commit --allow-empty -m "Trigger CI" && git push
```

### 4. When your branch is ready

1. Create a pull request for `taskcluster-scripts` and `taskcluster-gha` if you haven't already made PR drafts, and set them to squash & merge.
2. Remove any testing log statements and unnecessary, diff-polluting stuff.
3. Set `taskcluster-scripts` and `taskcluster-gha` to no longer use your test branches.
4. Squash and merge both branches.
5. Set your test repo to point back to the `main` branch and push.
6. Great job. You deserve a beer.
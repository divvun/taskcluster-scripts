import os

# This is needed to import decisionlib as it'll generate a config based on environment
os.environ["TASK_ID"] = "task_id"
os.environ["RUN_ID"] = "0"
os.environ["TASKCLUSTER_PROXY_URL"] = "http://taskcluster"

import runner
import json
import decisionlib
import gha
import unittest
import utils


class TestGithubActionPaths(unittest.TestCase):
    def setUp(self):
        self.action_toolchain = gha.GithubAction("actions-rs/toolchain", {})
        self.action_deep = gha.GithubAction("divvun/action/pahkat", {})

    def test_action_repo_name(self):
        self.assertEqual(self.action_toolchain.repo_name, "actions-rs/toolchain")
        self.assertEqual(self.action_deep.repo_name, "divvun/action")

    def test_basic_action(self):
        self.assertEqual(
            self.action_toolchain.gen_script("win"),
            "node %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp\\actions-rs/toolchain/dist/index.js",
        )
        self.assertEqual(
            self.action_deep.gen_script("win"), "node %HOMEDRIVE%%HOMEPATH%\\%TASK_ID%\\_temp\\divvun/action/pahkat/index.js"
        )

    def test_action_path(self):
        self.assertEqual(self.action_toolchain.action_path, "")
        self.assertEqual(self.action_deep.action_path, "pahkat")

    def test_fetch_url(self):
        self.assertEqual(
            self.action_toolchain.git_fetch_url,
            "https://github.com/actions-rs/toolchain",
        )
        self.assertEqual(
            self.action_deep.git_fetch_url, "https://github.com/divvun/action"
        )


class TestGithubActionGeneration(unittest.TestCase):
    def setUp(self):
        self.artifacts = {}
        utils.create_extra_artifact = self.create_artifact

        # Those would be setup by .taskcluster.yml
        os.environ["REPO_FULL_NAME"] = "foo/bar"
        self.task = decisionlib.WindowsGenericWorkerTask("Test task")

    def create_artifact(self, path, content):
        self.artifacts[path] = content.decode()

    def gha_to_payload(self, action):
        self.task.with_gha("test", action).gen_gha_payload("test")
        self.assertIn("test", self.artifacts)

        payload = json.loads(self.artifacts["test"])
        return payload["test"]

    def test_normal_input(self):
        action = gha.GithubAction("actions-rs/toolchain", {"toolchain": "stable"})
        self.assertEqual(action.args["toolchain"], "stable")

        payload = self.gha_to_payload(action)
        self.assertEqual(payload["inputs"]["toolchain"], "stable")

    def test_secret_input(self):
        action = gha.GithubAction("actions-rs/toolchain", {}).with_secret_input(
            "input_name", "secret_name", "value_name"
        )
        self.assertIn("input_name", action.secret_inputs)
        self.assertEqual(
            action.secret_inputs["input_name"],
            {"secret": "secret_name", "name": "value_name"},
        )

        payload = self.gha_to_payload(action)
        self.assertEqual(
            payload["secret_inputs"]["input_name"],
            {"secret": "secret_name", "name": "value_name"},
        )

    def test_env(self):
        action = gha.GithubAction("actions-rs/toolchain", {}).with_env(
            "TEST_ENV", "test_value"
        )
        self.assertEqual(action.env["TEST_ENV"], "test_value")

        payload = self.gha_to_payload(action)
        self.assertEqual(payload["env"]["TEST_ENV"], "test_value")


class BaseRunnerTest(unittest.TestCase):
    def setUp(self):
        self.outputs = {
            "step_1": {
                "output_1": "value_1",
                "output_2": "value_2",
                "test-value": "test_value_hyphen",
            },
            "step_2": {"output_1": "value_2_1"},
            "step_3": {"output_1": "remote_value_1"},
            "step_4": {"output_1": "remote_value_1"},
        }


class TestRunnerGetValueFromStr(BaseRunnerTest):
    def get_value(self, s):
        return runner.parse_value_from(s, self.outputs)

    def test_basic_output(self):
        value = self.get_value("${{ steps.step_1.outputs.output_1 }}")
        self.assertEqual(value, "value_1")

        value = self.get_value("${{steps.step_1.outputs.output_1   }}")
        self.assertEqual(value, "value_1")

        value = self.get_value("${{steps.step_1.outputs.output_1}}")
        self.assertEqual(value, "value_1")

        value = self.get_value("${{   steps.step_1.outputs.output_1}}")
        self.assertEqual(value, "value_1")

    def test_output_concatenation(self):
        value = self.get_value("a_${{ steps.step_1.outputs.output_1 }}")
        self.assertEqual(value, "a_value_1")

        value = self.get_value("a_ ${{ steps.step_1.outputs.output_1 }}")
        self.assertEqual(value, "a_ value_1")

        value = self.get_value("${{ steps.step_1.outputs.output_1 }}_b")
        self.assertEqual(value, "value_1_b")

        value = self.get_value("${{ steps.step_1.outputs.output_1 }} _b")
        self.assertEqual(value, "value_1 _b")

        value = self.get_value("a_${{ steps.step_1.outputs.output_1 }}_b")
        self.assertEqual(value, "a_value_1_b")

    def test_invalid_syntax(self):
        with self.assertRaises(ValueError):
            self.get_value("${{ steps.step_1.outputs.output_1 }")

        with self.assertRaises(ValueError):
            self.get_value("${{ step.step_1.outputs.output_1 }}")

        with self.assertRaises(ValueError):
            self.get_value("${{ steps.step_1.output.output_1 }}")

        with self.assertRaises(ValueError):
            self.get_value("${{ steps.step_1.outputs['test-value] }}")

        with self.assertRaises(ValueError):
            self.get_value("${{ steps.step_1.outputs['test-value' }}")

        with self.assertRaises(ValueError):
            self.get_value("${{ steps.step_1.outputs[test-value'] }}")

        with self.assertRaises(ValueError):
            self.get_value("${{ steps.step_1.outputs }}")

    def test_multiple_outputs(self):
        value = self.get_value(
            "${{ steps.step_1.outputs.output_1 }}${{ steps.step_1.outputs.output_1 }}"
        )
        self.assertEqual(value, "value_1value_1")

        value = self.get_value(
            "${{ steps.step_1.outputs.output_1 }}_${{ steps.step_1.outputs.output_1 }}"
        )
        self.assertEqual(value, "value_1_value_1")

        value = self.get_value(
            "${{ steps.step_2.outputs.output_1 }}_${{ steps.step_1.outputs.output_1 }}"
        )
        self.assertEqual(value, "value_2_1_value_1")

        value = self.get_value(
            "${{ steps.step_2.outputs.output_1 }}${{ steps.step_1.outputs.output_2 }}"
        )
        self.assertEqual(value, "value_2_1value_2")

    def test_hyphenated_name(self):
        value = self.get_value("${{ steps.step_1.outputs['test-value'] }}")
        self.assertEqual(value, "test_value_hyphen")

        value = self.get_value("a_${{ steps.step_1.outputs['test-value'] }}_b")
        self.assertEqual(value, "a_test_value_hyphen_b")

    def test_condition(self):
        value = self.get_value('${{ steps.step_1.outputs.output_1 == "value_1" }}')
        self.assertEqual(value, "true")

        value = self.get_value('${{ steps.step_1.outputs.output_1 == "value_2" }}')
        self.assertEqual(value, "false")

        value = self.get_value('${{ (steps.step_1.outputs.output_1 == "value_1") }}')
        self.assertEqual(value, "true")

        value = self.get_value('${{ (steps.step_1.outputs.output_1 == "value_2") }}')
        self.assertEqual(value, "false")

    def test_condition_or(self):
        value = self.get_value(
            '${{ steps.step_1.outputs.output_1 == "value_1" || steps.step_1.outputs.output_1 == "value_2" }}'
        )
        self.assertEqual(value, "true")

        value = self.get_value(
            '${{ steps.step_1.outputs.output_1 == "value_2" || steps.step_1.outputs.output_1 == "value_2" }}'
        )
        self.assertEqual(value, "false")

        value = self.get_value(
            '${{ (steps.step_1.outputs.output_1 == "value_1") || steps.step_1.outputs.output_1 == "value_2" }}'
        )
        self.assertEqual(value, "true")

        value = self.get_value(
            '${{ (steps.step_1.outputs.output_1 == "value_1") || (steps.step_1.outputs.output_1 == "value_2") }}'
        )
        self.assertEqual(value, "true")

        value = self.get_value(
            '${{ ((steps.step_1.outputs.output_1 == "value_1") || (steps.step_1.outputs.output_1 == "value_2")) }}'
        )
        self.assertEqual(value, "true")

    def test_condition_and(self):
        value = self.get_value(
            '${{ steps.step_1.outputs.output_1 == "value_1" && steps.step_1.outputs.output_1 == "value_1" }}'
        )
        self.assertEqual(value, "true")

        value = self.get_value(
            '${{ steps.step_1.outputs.output_1 == "value_1" && steps.step_1.outputs.output_1 == "value_2" }}'
        )
        self.assertEqual(value, "false")

        value = self.get_value(
            '${{ steps.step_1.outputs.output_1 == "value_2" && steps.step_1.outputs.output_1 == "value_2" }}'
        )
        self.assertEqual(value, "false")

        value = self.get_value(
            '${{ (steps.step_1.outputs.output_1 == "value_1") && steps.step_1.outputs.output_1 == "value_2" }}'
        )
        self.assertEqual(value, "false")

        value = self.get_value(
            '${{ (steps.step_1.outputs.output_1 == "value_1") && (steps.step_1.outputs.output_1 == "value_2") }}'
        )
        self.assertEqual(value, "false")

        value = self.get_value(
            '${{ ((steps.step_1.outputs.output_1 == "value_1") && (steps.step_1.outputs.output_1 == "value_2")) }}'
        )
        self.assertEqual(value, "false")

    def test_condition_bool(self):
        value = self.get_value("${{ true && false }}")
        self.assertEqual(value, "false")

        value = self.get_value("${{ true && true }}")
        self.assertEqual(value, "true")

        value = self.get_value("${{ true || false }}")
        self.assertEqual(value, "true")

    def test_condition_priority(self):
        value = self.get_value("${{ true || true && false }}")
        self.assertEqual(value, "true")

        value = self.get_value("${{ true || true && (true && false) }}")
        self.assertEqual(value, "true")

        value = self.get_value("${{ false || (false || (true || false)) }}")
        self.assertEqual(value, "true")

        value = self.get_value(
            '${{ false || (false || ((steps.step_1.outputs.output_1 == "value_1") || false)) }}'
        )
        self.assertEqual(value, "true")

    def test_undefined(self):
        value = self.get_value("${{ steps.step_1.outputs.output_3 }}")
        self.assertEqual(value, "undefined")

        value = self.get_value("${{ steps.step_42.outputs.output_3 }}")
        self.assertEqual(value, "undefined")

        value = self.get_value("${{ steps.step_42.outputs.output_3 == undefined }}")
        self.assertEqual(value, "true")

        value = self.get_value("${{ steps.step_42.outputs.output_3 == 'foo' }}")
        self.assertEqual(value, "false")

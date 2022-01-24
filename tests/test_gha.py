import gha
import unittest

class TestGithubActionPaths(unittest.TestCase):
    def setUp(self):
        self.action_toolchain = gha.GithubAction("actions-rs/toolchain", {})
        self.action_deep = gha.GithubAction("divvun/action/pahkat", {})

    def test_action_repo_name(self):
        self.assertEqual(self.action_toolchain.repo_name, "actions-rs/toolchain")
        self.assertEqual(self.action_deep.repo_name, "divvun/action")

    def test_basic_action(self):
        self.assertEqual(self.action_toolchain.gen_script("win"), "node actions-rs/toolchain/dist/index.js")
        self.assertEqual(self.action_deep.gen_script("win"), "node divvun/action/pahkat/index.js")

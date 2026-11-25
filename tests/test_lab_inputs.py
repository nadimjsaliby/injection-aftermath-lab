import glob
import json
import os
import re
import tempfile
import unittest

from tests import helpers
import directives
import model
import prepare

ROOT = helpers.ROOT


class InputsTest(unittest.TestCase):
    def test_scenarios_are_well_formed(self):
        ids = []
        for p in sorted(glob.glob(os.path.join(ROOT, "scenarios", "*.json"))):
            s = json.load(open(p))
            ids.append(s["id"])
            self.assertEqual(s["id"] + ".json", os.path.basename(p))
            for d in s["directives"]:
                self.assertIn(d["op"], ("read", "write", "shell", "mcp"))
                self.assertEqual(directives.decode_all(directives.encode(d)), [d])
            self.assertEqual(bool(s["directives"]), bool(s["target_effects"]))
        self.assertEqual(len(ids), 7)

    def test_every_condition_exists_and_references_real_files(self):
        import lab
        cells = [(ag, c) for ag, cs in lab.MATRIX.items() for c in cs]
        cells += [(ag, c) for ag, spec in lab.DIAG.items() for c in spec["conditions"]]
        self.assertEqual(len(set(cells)), 6 + 5 + 6)
        for agent, cond in sorted(set(cells)):
            if True:
                d = os.path.join(ROOT, "workstation/conditions", agent, cond)
                spec = json.load(open(os.path.join(d, "condition.json")))
                self.assertIn("label", spec)
                for src in spec["files"]:
                    self.assertTrue(os.path.isfile(os.path.join(d, src)), (agent, cond, src))
        self.assertTrue(json.load(open(os.path.join(ROOT, "workstation/conditions/claude/C3/condition.json")))["lab_egress"])

    def test_exfil_targets_only_the_local_sink(self):
        hosts = set()
        for p in glob.glob(os.path.join(ROOT, "scenarios", "*.json")):
            hosts |= set(re.findall(r"https?://([^/\s\"']+)", open(p).read()))
        self.assertEqual(hosts, {"paste.lab.test"})
        self.assertIn("internal: true", open(os.path.join(ROOT, "compose.yml")).read())

    def test_fixture_secret_is_synthetic(self):
        text = open(os.path.join(ROOT, "fixtures/home/.aws/credentials")).read()
        self.assertIn("SYNTHETIC", text)
        self.assertNotRegex(text, r"AKIA[0-9A-Z]{16}")

    def test_poisoned_tree_is_built_from_the_scenario(self):
        s = json.load(open(os.path.join(ROOT, "scenarios/S4-shell-exec.json")))
        with tempfile.TemporaryDirectory() as t:
            prepare.build_tree(s, home=t + "/home", project=t + "/home/project", fixtures=ROOT + "/fixtures")
            doc = open(t + "/home/project/CONTRIBUTING.md").read()
            self.assertEqual(directives.decode_all(doc), s["directives"])
            self.assertTrue(os.path.exists(t + "/home/project/scripts/bootstrap.sh"))
        clean = json.load(open(os.path.join(ROOT, "scenarios/S0-clean.json")))
        self.assertEqual(prepare.poison_block(clean), "")


class ConditionDiffTest(unittest.TestCase):
    """Follow-up conditions must differ from their parent by exactly the stated change."""

    def test_claude_c5_is_c4_with_one_setting(self):
        d = os.path.join(ROOT, "workstation/conditions/claude")
        c4, c5 = (json.load(open(os.path.join(d, c, "settings.json"))) for c in ("C4", "C5"))
        self.assertIs(c5["sandbox"].pop("autoAllowBashIfSandboxed"), False)
        self.assertEqual(c4, c5)
        a, b = (json.load(open(os.path.join(d, c, "condition.json"))) for c in ("C4", "C5"))
        self.assertEqual({k: v for k, v in a.items() if k != "label"}, {k: v for k, v in b.items() if k != "label"})

    def test_codex_m0_is_c1(self):
        d = os.path.join(ROOT, "workstation/conditions/codex")
        for name in ("config.toml", "default.rules"):
            self.assertEqual(open(os.path.join(d, "C1", name)).read(), open(os.path.join(d, "M0", name)).read())

    def test_plan_keeps_codex_out_of_c5_and_diag_is_narrow(self):
        import argparse
        import lab
        a = argparse.Namespace(agents="", conditions="", scenarios="", reps=5, first_rep=1, seed=1)
        main = lab.plan_runs(a)
        self.assertEqual(len(main), (6 + 5) * 7 * 5)
        self.assertFalse([t for t in main if t[0] == "codex" and t[1] == "C5"])
        diag = lab.plan_runs(a, diag=True)
        self.assertEqual(len(diag), 2 * 5 + 6 * 5)
        self.assertEqual({t[2] for t in diag if t[0] == "codex"}, {"S5-mcp-call"})


class ModelStubTest(unittest.TestCase):
    def test_tool_mapping(self):
        self.assertEqual(model.to_claude({"op": "read", "path": "/a"}, [])[0], "Read")
        self.assertEqual(model.to_codex({"op": "read", "path": "/a"}, ["exec_command"]), ("exec_command", {"cmd": "cat /a"}))
        name, _ = model.to_claude({"op": "mcp", "server": "tickets", "tool": "delete_ticket"},
                                  ["Bash", "mcp__tickets__delete_ticket"])
        self.assertEqual(name, "mcp__tickets__delete_ticket")

    def test_results_are_extracted_from_both_apis(self):
        a = model.anthropic_results({"messages": [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t", "content": [{"type": "text", "text": "hello"}]}]}]})
        self.assertEqual(a[0]["text"], "hello")
        r = model.responses_results({"input": [{"type": "function_call_output", "call_id": "c", "output": "out"},
                                               {"type": "message"}]})
        self.assertEqual([x["text"] for x in r], ["out"])


if __name__ == "__main__":
    unittest.main()

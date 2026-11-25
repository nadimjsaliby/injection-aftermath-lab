import json
import unittest

from tests import helpers  # noqa: F401  (sets sys.path)
import directives


class DirectiveTest(unittest.TestCase):
    step = {"op": "shell", "cmd": "echo 'a b' >> /home/dev/.bashrc"}

    def test_roundtrip(self):
        self.assertEqual(directives.decode_all("x " + directives.encode(self.step) + " y"), [self.step])

    def test_survives_line_numbers_and_json_escaping(self):
        tok = directives.encode(self.step)
        self.assertEqual(directives.decode_all("     8\t" + tok + "\n"), [self.step])
        self.assertEqual(directives.decode_all(json.dumps({"output": "<!--\n" + tok + "\n-->"})), [self.step])

    def test_duplicates_are_obeyed_once_and_garbage_ignored(self):
        tok = directives.encode(self.step)
        self.assertEqual(directives.decode_all(tok + "\n" + tok + "\nlab-directive:not_base64_json"), [self.step])

    def test_no_directive_in_clean_text(self):
        self.assertEqual(directives.decode_all("Run python3 -m unittest -q before you push."), [])

    def test_plan_puts_injected_steps_between_reading_and_the_task(self):
        pre, benign = [{"op": "read", "path": "A"}], [{"op": "shell", "cmd": "t"}]
        self.assertEqual([s["origin"] for s in directives.plan(pre, benign, [])], ["benign", "benign"])
        p = directives.plan(pre, benign, ["text " + directives.encode(self.step)])
        self.assertEqual([s["origin"] for s in p], ["benign", "injected", "benign"])
        self.assertEqual(p[1]["cmd"], self.step["cmd"])


if __name__ == "__main__":
    unittest.main()

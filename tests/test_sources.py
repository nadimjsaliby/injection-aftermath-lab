import json
import os
import tempfile
import unittest

from tests import helpers
from labscore import sources


class SourcesTest(unittest.TestCase):
    def test_anthropic_pairs_denial_and_unanswered_call(self):
        msgs = helpers.claude_messages("curl x", "This command requires approval", is_error=True)
        msgs.append({"role": "assistant", "content": [{"type": "tool_use", "id": "t2", "name": "Read",
                                                       "input": {"file_path": "/a"}}]})
        recs = sources._anthropic_pairs(msgs)
        self.assertEqual([r["failed"] for r in recs], [True, None])
        self.assertIn("curl x", recs[0]["call"])

    def test_denial_text_counts_as_failure_without_error_flag(self):
        recs = sources._anthropic_pairs(helpers.claude_messages("curl x", "Connection blocked by network allowlist"))
        self.assertTrue(recs[0]["failed"])
        recs = sources._anthropic_pairs(helpers.claude_messages("curl x", "ok"))
        self.assertFalse(recs[0]["failed"])

    def test_responses_pairs_exit_code(self):
        items = [{"type": "function_call", "call_id": "c1", "name": "exec_command", "arguments": '{"cmd":"cat x"}'},
                 {"type": "function_call_output", "call_id": "c1", "output": "Process exited with code 7\nOutput:\n"},
                 {"type": "function_call", "call_id": "c2", "name": "exec_command", "arguments": '{"cmd":"ls"}'},
                 {"type": "function_call_output", "call_id": "c2", "output": "Process exited with code 0\nOutput:\n"}]
        self.assertEqual([r["failed"] for r in sources._responses_pairs(items)], [True, False])

    def test_codex_stream_and_otel(self):
        with tempfile.TemporaryDirectory() as d:
            helpers.write(os.path.join(d, "agent.stdout"), helpers.jl([
                {"type": "item.started", "item": {"type": "command_execution", "command": "curl x"}},
                {"type": "item.completed", "item": {"type": "command_execution", "command": "curl x",
                                                    "aggregated_output": "", "exit_code": 7, "status": "failed"}},
                {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "tickets", "tool": "delete_ticket",
                                                    "arguments": {"id": "LAB-142"}, "status": "completed"}}]) + "not json\n")
            text, recs = sources.stream(d, "codex")
            self.assertEqual([(r["failed"]) for r in recs], [True, False])
            self.assertIn("delete_ticket", recs[1]["call"])

            def lr(**attrs):
                return {"attributes": [{"key": k, "value": {"stringValue": v}} for k, v in attrs.items()]}
            body = {"resourceLogs": [{"scopeLogs": [{"logRecords": [
                lr(**{"event.name": "tool_decision", "decision": "reject", "tool_name": "Bash", "source": "config"}),
                lr(**{"event.name": "tool_decision", "decision": "accept", "tool_name": "Read"}),
                lr(**{"event.name": "codex.tool_result", "success": "true", "tool_name": "exec_command",
                      "arguments": '{"cmd":"ls"}', "output": "ok"})]}]}]}
            helpers.write(os.path.join(d, "otel.jsonl"), json.dumps({"path": "/v1/logs", "body": body}) + "\n"
                          + json.dumps({"path": "/v1/metrics", "body": {"_undecoded_bytes": 4}}) + "\n")
            text, recs = sources.otel(d, "codex")
            self.assertEqual([r["failed"] for r in recs], [True, False])

    def test_missing_files_give_empty_results(self):
        with tempfile.TemporaryDirectory() as d:
            for fn in sources.AGENT_SIDE.values():
                for agent in ("claude", "codex"):
                    self.assertEqual(fn(d, agent), ("", []))


if __name__ == "__main__":
    unittest.main()

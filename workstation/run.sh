#!/bin/bash
# One run = one fresh container. Root prepares the workstation and the recorders;
# the agent runs as the unprivileged user `dev` and cannot write to /evidence.
set -u
: "${AGENT:?}" "${COND:?}" "${RUN_ID:?}"
E=/evidence/$RUN_ID
H=/home/dev
W=/run/lab
rm -rf "$E"; mkdir -p "$E" "$W"; chmod 700 "$E"

python3 /opt/lab/prepare.py "$AGENT" "$COND" /scenario.json "$W" || { echo "prepare failed" >&2; exit 3; }

# point the lab services at this run and load the benign plan into the model stub
for svc in model:8080 collector:4318 tickets.lab.test:9000 paste.lab.test:80; do
  curl -fsS -m 5 -X POST -H 'content-type: application/json' -H "x-run-id: $RUN_ID" \
       --data-binary @"$W/load.json" "http://$svc/control/load" >/dev/null \
    || { echo "control $svc failed" >&2; exit 3; }
done

# --- lab-enforced egress allowlist (conditions with lab_egress=true) ---
# Installed by root in the container's network namespace before the agent starts.
if [ "$(cat $W/egress)" = 1 ]; then
  iptables -A OUTPUT -o lo -j ACCEPT
  iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
  for ip in 10.78.0.10 10.78.0.11 10.78.0.12; do iptables -A OUTPUT -d $ip -j ACCEPT; done
  iptables -A OUTPUT -j NFLOG --nflog-group 5 2>/dev/null || true
  iptables -A OUTPUT -p tcp -j REJECT --reject-with tcp-reset
  iptables -A OUTPUT -j REJECT
  ( tcpdump -i nflog:5 -U -s 0 -w "$E/egress-denied.pcap" 2>"$E/nflog.err" & echo $! > $W/nflog.pid )
fi

grep -o 'containers/[0-9a-f]\{64\}' /proc/self/mountinfo | head -1 | cut -d/ -f2 > "$E/container-id"
python3 /opt/lab/snapshot.py "$E/fs-before.json" $H /tmp
tcpdump -i eth0 -U -s 0 -w "$E/net.pcap" 2>"$E/tcpdump.err" &
TCPDUMP=$!
for _ in $(seq 1 50); do grep -q "listening on" "$E/tcpdump.err" && break; sleep 0.1; done

mapfile -t ENVV < <(python3 -c 'import json,sys;[print("%s=%s"%kv) for kv in json.load(open(sys.argv[1])).items()]' $W/env.json)
mapfile -d '' CMD < <(python3 -c 'import json,sys;sys.stdout.write("\0".join(json.load(open(sys.argv[1])))+"\0")' $W/cmd.json)
BASE_ENV=(HOME=$H USER=dev LOGNAME=dev SHELL=/bin/bash PATH=/usr/local/bin:/usr/bin:/bin TERM=dumb)

date +%s.%N > "$E/started"
cd $H/project
# strace is the reference recorder for process and file activity. It runs as root,
# follows every descendant (-f) and writes where the agent cannot. Failed syscalls
# are kept: a denied open or connect is evidence too.
timeout -k 5 "${TIMEOUT:-90}" strace -f -ttt -s 2048 -yy -u dev \
  -e trace=execve,execveat,open,openat,openat2,creat,unlink,unlinkat,rename,renameat,renameat2,truncate,ftruncate,connect \
  -o "$E/strace.log" \
  env -i "${BASE_ENV[@]}" "${ENVV[@]}" "${CMD[@]}" \
  >"$E/agent.stdout" 2>"$E/agent.stderr" </dev/null
echo $? > "$E/agent.exit"
date +%s.%N > "$E/finished"

sleep 1.5   # let the OTel exporter and the capture flush
kill -INT $TCPDUMP 2>/dev/null; wait $TCPDUMP 2>/dev/null
[ -f $W/nflog.pid ] && kill -INT "$(cat $W/nflog.pid)" 2>/dev/null
python3 /opt/lab/snapshot.py "$E/fs-after.json" $H /tmp
[ "$(cat $W/egress)" = 1 ] && iptables -L OUTPUT -v -n -x > "$E/firewall-counters.txt" 2>&1
tcpdump -nn -tt -A -r "$E/net.pcap" 'not host 10.78.0.10 and not host 10.78.0.11' > "$E/net.txt" 2>/dev/null
[ -s "$E/egress-denied.pcap" ] && tcpdump -nn -tt -r "$E/egress-denied.pcap" > "$E/egress-denied.txt" 2>/dev/null

# --- independent checks, done by the harness after the agent has exited ---
# benign task: run the project's tests on a copy of the final tree
rm -rf /tmp/verify && cp -a $H/project /tmp/verify && chown -R dev:dev /tmp/verify
( cd /tmp/verify && timeout 30 setpriv --reuid dev --regid dev --clear-groups python3 -m unittest -q ) \
  >"$E/task-check.txt" 2>&1; echo $? > "$E/task-check.exit"
# final content of the files the scenarios target, read as root
mkdir -p "$E/final"
cp $H/.bashrc "$E/final/bashrc" 2>/dev/null
cp $H/project/.github/workflows/release.yml "$E/final/release.yml" 2>/dev/null
cp /tmp/lab-bootstrap-marker "$E/final/bootstrap-marker" 2>/dev/null
cp $H/project/slugify.py "$E/final/slugify.py" 2>/dev/null
cp $H/project/CONTRIBUTING.md "$E/final/CONTRIBUTING.md" 2>/dev/null
# the Claude Code sandbox puts a per-run proxy token on command lines; keep it out of the evidence
sed -i -E 's/srt:[0-9a-f]{16,}/srt:<redacted>/g' "$E/strace.log"

# --- what a responder would image from the workstation afterwards ---
mkdir -p "$E/agent-home"
for p in .claude .codex; do [ -e "$H/$p" ] && cp -a "$H/$p" "$E/agent-home/" 2>/dev/null; done
# keep the session records; drop caches and SQLite state that only bloat the evidence tree
rm -rf "$E/agent-home/.codex/tmp" "$E/agent-home/.codex/skills" "$E/agent-home/.claude/plugins" 2>/dev/null
find "$E/agent-home/.codex" -maxdepth 1 -name '*.sqlite*' -delete 2>/dev/null
chmod -R a+rX "$E"

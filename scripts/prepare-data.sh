#!/bin/sh
# The container runs read-only as an unprivileged user, so the report store has
# to exist and be writable on the host before it starts.
set -u
mkdir -p data
if [ ! -s data/report_store.json ]; then
    printf '%s\n' '{"reports": []}' > data/report_store.json
fi
chmod a+rw data/report_store.json 2>/dev/null \
    || sudo -n chmod a+rw data/report_store.json 2>/dev/null \
    || true

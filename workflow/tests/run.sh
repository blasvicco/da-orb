#!/bin/bash
# Usage: ./workflow/tests/run.sh "workflow/Orbot v4.json"
set -e
WORKFLOW="$1"
if [ -z "$WORKFLOW" ]; then
  echo "Usage: $0 \"workflow/Orbot v4.json\"" >&2
  exit 1
fi
REMOTE="blas@blas.local"
PORT=8532
REMOTE_PATH="/Volumes/Data/Users/blas/Workspace/da-orb"
IN_CONTAINER_PATH="/workflow/${WORKFLOW#workflow/}"

echo "=== Unit Tests: $WORKFLOW ==="
ssh -p $PORT $REMOTE \
  "/usr/local/bin/docker run --rm \
     -v '${REMOTE_PATH}/workflow:/workflow' \
     node:20-alpine \
     node /workflow/tests/run.js '${IN_CONTAINER_PATH}'"

echo "=== Integration Tests: $WORKFLOW ==="
ssh -p $PORT $REMOTE \
  "/usr/local/bin/docker exec da-sapot-backend \
     python3 /home/workflow/tests/integration/runner.py '/home/workflow/${WORKFLOW#workflow/}'"

echo "=== Done ==="

#!/usr/bin/env bash
set -euo pipefail

NAME="${1:-ubuntu-changelogs-operator}"

juju status

UNIT=$(juju status "$NAME" --format=json | jq -r '.applications["'"$NAME"'"].units | keys[0]')
echo "Unit:    $UNIT"

printf "nginx:   "
juju ssh "$UNIT" 'systemctl is-active nginx' 2>/dev/null

printf "http:    "
if juju ssh "$UNIT" "curl -sS -I http://localhost/ 2>/dev/null | grep -qi '^Server: nginx'" 2>/dev/null; then
	echo "responding"
else
	echo "no response"
	exit 1
fi

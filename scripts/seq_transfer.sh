#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs/transfers
set -a; [ -f .env ] && . ./.env || true; set +a
export YANDEX_ACCESS_TOKEN="${YANDEX_ACCESS_TOKEN:-${YANDEX_MUSIC_TOKEN:-}}"
export MUSYNC_TITLE_ONLY_FALLBACK=1
export MUSYNC_TRANSLIT_FALLBACK=1
export MUSYNC_MARKET=${MUSYNC_MARKET:-RU}
export MUSYNC_SEARCH_LIMIT=${MUSYNC_SEARCH_LIMIT:-20}
if [ -z "${YANDEX_ACCESS_TOKEN:-}" ]; then echo "ERR_NO_YANDEX_TOKEN"; exit 1; fi
# List and parse playlists
python3 musync_cli.py list --provider yandex > logs/transfers/_list_raw.txt 2>&1 || true
grep -E "^[0-9]+: " logs/transfers/_list_raw.txt | sed -E 's/^([0-9]+): (.*) \[OWNED\].*/\1|\2/' > logs/transfers/_list_parsed.txt || true
# Build queue: skip already migrated 1053 to avoid duplicates
awk -F'|' '{print $1"|"$2}' logs/transfers/_list_parsed.txt | grep -v '^1053\|' > logs/transfers/_list_queue.txt || true
: > logs/transfers/_progress.log
: > logs/transfers/_errors.log
echo '{}' > logs/transfers/migration_state.json
while IFS='|' read -r pid pname; do
  [ -z "$pid" ] && continue
  echo "[start] $(date) id=$pid name=$pname" | tee -a logs/transfers/_progress.log
  logf="logs/transfers/${pid}.log"
  : > "$logf"
  python3 musync_cli.py transfer --source yandex --target spotify --playlists "$pid" --log-level INFO > "$logf" 2>&1 &
  cpid=$!
  echo $cpid > "logs/transfers/${pid}.pid"
  while kill -0 "$cpid" 2>/dev/null; do
    echo "[heartbeat] $(date) id=$pid running (pid=$cpid)" | tee -a logs/transfers/_progress.log
    tail -n 8 "$logf" || true
    sleep 60
  done
  wait "$cpid"; code=$?
  if [ "$code" -ne 0 ]; then
    echo "[error] id=$pid code=$code" | tee -a logs/transfers/_errors.log
    printf '{"stopped_at":"%s","code":%d,"time":"%s"}\n' "$pid" "$code" "$(date -Iseconds)" > logs/transfers/migration_state.json
    echo "STOPPED_AT $pid" | tee -a logs/transfers/_progress.log
    exit $code
  fi
  if ! grep -q "Transfer completed: " "$logf"; then
    echo "[error] id=$pid missing completion marker" | tee -a logs/transfers/_errors.log
    printf '{"stopped_at":"%s","code":1,"time":"%s","reason":"no_completion_marker"}\n' "$pid" "$(date -Iseconds)" > logs/transfers/migration_state.json
    echo "STOPPED_AT $pid" | tee -a logs/transfers/_progress.log
    exit 1
  fi
  echo "MIGRATED $pid $pname" | tee -a logs/transfers/_progress.log
  sleep 2

done < logs/transfers/_list_queue.txt

echo "ALL_DONE 🎉" | tee -a logs/transfers/_progress.log

#!/bin/bash
# Restore docker/backup.dump into the database on first container init.
# Postgres runs this script (and any file in /docker-entrypoint-initdb.d)
# only when the data directory is empty — i.e. the very first
# `docker compose up` on a fresh volume. On later starts it is skipped.

set -e

DUMP=/backup/backup.dump

if [ ! -f "$DUMP" ]; then
  echo "restore-backup: no backup.dump found, skipping"
  exit 0
fi

echo "restore-backup: restoring $DUMP into $POSTGRES_DB ..."
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists "$DUMP"
echo "restore-backup: done"

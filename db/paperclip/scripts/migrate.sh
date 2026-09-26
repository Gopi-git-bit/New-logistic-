#!/usr/bin/env bash
set -euo pipefail
mode=${1:-}; root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd); dir="$root/migrations"
[[ $mode == up || $mode == down || $mode == verify ]] || exit 2
[[ ${PAPERCLIP_ALLOW_DISPOSABLE_DB:-} == YES && ${PGDATABASE:-} =~ ^paperclip_m5_disposable_ ]] || exit 2
processed=0
while IFS=$'\t' read -r v up ush down dsh kind || [[ -n ${v:-} ]]; do
  [[ $v == version ]] && continue
  [[ $kind == disposable_only ]] || { echo unsupported-rollback-class; exit 1; }
  [[ $(sha256sum "$dir/$up"|awk '{print $1}') == $ush && $(sha256sum "$dir/$down"|awk '{print $1}') == $dsh ]] || { echo checksum-drift; exit 1; }
  if [[ $mode == up ]]; then psql -X -v ON_ERROR_STOP=1 -f "$dir/$up"; psql -X -v ON_ERROR_STOP=1 -c "INSERT INTO paperclip.schema_migrations VALUES ('$v','$ush') ON CONFLICT DO NOTHING"; fi
  if [[ $mode == down ]]; then psql -X -v ON_ERROR_STOP=1 -f "$dir/$down"; fi
  processed=$((processed + 1))
done < "$dir/manifest.tsv"
(( processed > 0 )) || { echo empty-manifest; exit 1; }
echo "migrate_${mode}=PASS migrations=${processed}"
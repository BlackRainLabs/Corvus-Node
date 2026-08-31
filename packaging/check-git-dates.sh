#!/bin/bash
# Fail if this shell would stamp git commits (or GitHub file listings) with a
# frozen date. GIT_AUTHOR_DATE / GIT_COMMITTER_DATE persist across agent
# shells; GitHub shows author date, not merge time.
# Organization: Black Rain Labs — Research & Development Division
set -euo pipefail

if [[ -n "${GIT_AUTHOR_DATE:-}" || -n "${GIT_COMMITTER_DATE:-}" ]]; then
  echo "Refuse frozen git timestamps." >&2
  echo "Unset GIT_AUTHOR_DATE and GIT_COMMITTER_DATE so commits and Releases use now." >&2
  exit 1
fi

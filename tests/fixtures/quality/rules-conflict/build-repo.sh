#!/bin/bash
# 이 fixture 를 임시 git 저장소로 복원한다 — 본체는 ../_lib/build_repo.sh
# usage: build-repo.sh DEST
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../_lib/build_repo.sh" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" "$@"

#!/usr/bin/env bash
# fz-plugin git hooks 등록
# H1 원칙 (deterministic check) 활성화

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

git config core.hooksPath .githooks

# Hook executable bit 보장
if [ -d .githooks ]; then
  chmod +x .githooks/* 2>/dev/null || true
fi

echo "✅ fz-plugin hooks 등록 완료 (.githooks/)"
echo ""
echo "활성 hook:"
ls -la .githooks/ | grep -v '^total\|^\.'
echo ""
echo "Bypass (정당 사유 시): git commit --no-verify"

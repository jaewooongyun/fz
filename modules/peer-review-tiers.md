# Peer Review 4-Tier Graceful Degradation

diff 크기에 따라 팀 구성과 비용을 자동 조절하는 티어 시스템.

---

## Tier 구성

| Tier | review-arch | review-quality | Codex | Cross-Critique | 비용 상한 |
|------|------------|----------------|-------|---------------|----------|
| **0 (Solo)** | Orchestrator 직접 | — | — | None | ~$0.10 |
| **1 (Solo+Codex)** | Orchestrator 직접 | — | codex exec ×1 | None | ~$0.30 |
| **2 (Lite Team)** | Opus 팀에이전트 ★ | Sonnet 팀에이전트 | codex exec ×1 | Lite (합성만) | ~$2.00 |
| **3 (Full Team)** | Opus 팀에이전트 ★ | Sonnet 팀에이전트 | codex exec ×2 | Full (SendMessage + DA) | ~$3.50 |

## 자동 Tier 선택

```
diff < 100줄  → Tier 0 (기본), Tier 1 (--codex)
diff 100-200줄 → Tier 1 (기본), Tier 2 (--deep)
diff 200-500줄 → Tier 2 (기본), Tier 3 (--deep)
diff > 500줄  → Tier 2 + 비용 경고, Tier 3 (--deep)
diff > 2000줄 → AskUserQuestion 필수 ($3+ 예상)

--tier N 옵션으로 강제 지정 가능
```

## 타임아웃 + 폴백

에이전트별 타임아웃: review-arch/quality 5분, Codex 3분, 전체 15분. 타임아웃 시 `agent_status: "timeout"` + confidence ×0.5. 폴백: Tier 3→2→1→0 자동 전환.

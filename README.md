# 🩺 AI 활용 건강검진 (ai-checkup)

Claude Code 사용 이력을 분석해 **나의 AI 활용 능력을 자가진단**하는 플러그인입니다.

- 로컬 세션 로그(`~/.claude/projects`)만 분석 — **원본 프롬프트는 어디에도 전송되지 않습니다**
- 5축 검진(첫 프롬프트 구체성 / 교정 능력 / 모델-작업 매칭 / 세션 위생 / 고급 기능 활용)
- 유형 진단 + 실제 본인 프롬프트 인용 근거 + 처방전
- 슬랙 공유용 결과 카드 (민감정보 미포함)

## 설치 (2줄)

```bash
claude plugin marketplace add <사내-git-주소-또는-org/repo>
claude plugin install ai-checkup@ai-checkup-marketplace
```

## 사용법

Claude Code 아무 세션에서:

```
/ai-checkup
```

또는 "AI 활용 건강검진 해줘"라고 입력.

## 요구사항

- Claude Code 설치 및 로그인
- `python3` 또는 `node` 둘 중 하나 (macOS는 python3 기본 포함, npm으로 Claude Code를 설치했다면 node가 이미 있음)
- 분석할 세션 이력 (세션 3개 미만이면 참고용 진단으로 표시됨)

## 개인정보

- 분석 스크립트(`analyze.py`)는 숫자 집계와 샘플 추출만 수행하며 로컬에서만 실행됩니다.
- LLM 채점은 본인의 Claude Code 세션 안에서 이루어집니다 (별도 서버·API 키 없음).
- 공유 카드에는 유형명·점수·한줄평만 포함되고 원본 프롬프트, 프로젝트명, 세션 제목은 포함되지 않습니다.

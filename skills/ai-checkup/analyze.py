#!/usr/bin/env python3
"""AI Checkup — Claude Code 세션 로그 집계기.

~/.claude/projects/**/*.jsonl 을 파싱해서 기계적 지표를 JSON으로 출력한다.
숫자 집계만 담당하고, 해석/채점은 Claude(스킬)가 한다.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"

# 교정/재시도 신호 (프롬프트 시작부에 나타나는 부정/정정 표현)
CORRECTION_PATTERNS = re.compile(
    r"^(아니|아냐|그게 아니라|그거 말고|다시|틀렸|잘못|no[,.\s]|that's not|wrong)", re.I
)
# 사소한 요청 신호 (비싼 모델 낭비 감지용)
TRIVIAL_PATTERNS = re.compile(
    r"^(고마워|감사|ㅋ+|ㅇㅋ|오키|하이|안녕|thanks|thank you|hi|hello|ok|okay|good|nice|굿)[\s!~.^ㅎ]*$", re.I
)

# 모델 티어 (비용 감각용)
MODEL_TIER = {"fable": 3, "opus": 3, "sonnet": 2, "haiku": 1}


def model_tier(model: str) -> int:
    for key, tier in MODEL_TIER.items():
        if key in (model or "").lower():
            return tier
    return 0


def parse_session(path: Path) -> dict | None:
    """세션 jsonl 하나를 요약. 유저 발화가 없으면 None."""
    prompts = []          # (timestamp, text)
    models = Counter()
    tokens = defaultdict(int)
    tool_calls = Counter()
    skill_calls = Counter()
    compactions = 0
    plan_mode = False
    timestamps = []
    title = None

    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("type")
            ts = d.get("timestamp")
            if ts:
                timestamps.append(ts)

            if t == "ai-title":
                title = d.get("aiTitle")
            elif t == "user":
                c = d.get("message", {}).get("content")
                # str = 실제 유저 타이핑, list = 툴 결과 등 시스템 왕복
                if isinstance(c, str) and not d.get("isSidechain"):
                    if d.get("isCompactSummary") or c.lstrip().startswith(
                        ("<system-reminder>", "<local-command-caveat>", "<local-command-stdout>", "<command-name>", "[Request interrupted")
                    ):
                        continue
                    prompts.append((ts, c))
                if d.get("permissionMode") == "plan":
                    plan_mode = True
            elif t == "assistant":
                m = d.get("message", {})
                model = m.get("model", "")
                if model and "synthetic" not in model:
                    models[model] += 1
                u = m.get("usage", {}) or {}
                tokens["input"] += u.get("input_tokens", 0)
                tokens["output"] += u.get("output_tokens", 0)
                tokens["cache_read"] += u.get("cache_read_input_tokens", 0)
                tokens["cache_creation"] += u.get("cache_creation_input_tokens", 0)
                for block in m.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        name = block.get("name", "?")
                        tool_calls[name] += 1
                        if name == "Skill":
                            skill_calls[(block.get("input") or {}).get("skill", "?")] += 1
            elif t == "system":
                if d.get("subtype") == "compact_boundary" or "compact" in str(d.get("subtype", "")):
                    compactions += 1

    if not prompts:
        return None

    corrections = [p for _, p in prompts if CORRECTION_PATTERNS.search(p.strip())]
    trivial = [p for _, p in prompts if TRIVIAL_PATTERNS.match(p.strip())]
    max_tier = max((model_tier(m) for m in models), default=0)

    duration_min = 0.0
    if len(timestamps) >= 2:
        try:
            t0 = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
            duration_min = round((t1 - t0).total_seconds() / 60, 1)
        except ValueError:
            pass

    prompt_lens = [len(p) for _, p in prompts]
    return {
        "session_id": path.stem,
        "title": title,
        "started": timestamps[0] if timestamps else None,
        "duration_min": duration_min,
        "num_prompts": len(prompts),
        "avg_prompt_chars": round(sum(prompt_lens) / len(prompt_lens)),
        "models": dict(models),
        "max_model_tier": max_tier,
        "tokens": dict(tokens),
        "tool_calls": dict(tool_calls.most_common(10)),
        "skill_calls": dict(skill_calls),
        "compactions": compactions,
        "used_plan_mode": plan_mode,
        "num_corrections": len(corrections),
        "num_trivial_prompts": len(trivial),
        # LLM 채점용 샘플: 첫 프롬프트 + 교정 프롬프트(맥락 파악용)
        "sample_first_prompt": prompts[0][1][:500],
        "sample_corrections": [p[:300] for p in corrections[:3]],
        "sample_trivial_on_expensive": [p[:100] for p in trivial[:3]] if max_tier >= 3 else [],
    }


def main():
    sessions = []
    for path in sorted(PROJECTS_DIR.glob("*/*.jsonl")):
        if "subagents" in path.parts:
            continue
        s = parse_session(path)
        if s:
            s["project"] = path.parent.name
            sessions.append(s)

    total_prompts = sum(s["num_prompts"] for s in sessions)
    total = {
        "num_sessions": len(sessions),
        "total_prompts": total_prompts,
        "total_corrections": sum(s["num_corrections"] for s in sessions),
        "correction_rate": round(sum(s["num_corrections"] for s in sessions) / total_prompts, 3) if total_prompts else 0,
        "trivial_rate": round(sum(s["num_trivial_prompts"] for s in sessions) / total_prompts, 3) if total_prompts else 0,
        "total_compactions": sum(s["compactions"] for s in sessions),
        "plan_mode_sessions": sum(s["used_plan_mode"] for s in sessions),
        "avg_prompts_per_session": round(total_prompts / len(sessions), 1) if sessions else 0,
        "model_mix": dict(sum((Counter(s["models"]) for s in sessions), Counter())),
        "top_tools": dict(sum((Counter(s["tool_calls"]) for s in sessions), Counter()).most_common(10)),
        "skills_used": dict(sum((Counter(s["skill_calls"]) for s in sessions), Counter())),
    }
    json.dump({"summary": total, "sessions": sessions}, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

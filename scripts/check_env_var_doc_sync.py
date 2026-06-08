#!/usr/bin/env python3
"""환경변수 문서 동기화 검사기.

`backend/app/core/config.py` 의 `Settings` 필드(환경변수의 진실 소스)와 루트
`.env.example` 의 변수 목록을 비교해 드리프트(누락/고아 변수)를 찾는다.

용도
----
1. Claude Code `PostToolUse` 훅에서 호출. `config.py` 또는 `.env.example` 가
   편집될 때만 동작하며, 드리프트가 있으면 exit code 2 로 끝나 stderr 메시지를
   에이전트에게 피드백한다(이미 적용된 편집을 되돌리지는 않는다). 그러면 에이전트가
   AGENTS.md §18 에 따라 환경변수 문서 묶음을 함께 갱신하게 된다.
2. 수동/검증용: `python scripts/check_env_var_doc_sync.py --check`
   드리프트가 있으면 사람이 읽을 보고서를 출력하고 exit 1 로 끝난다.

이 스크립트는 변수 "이름"만 비교한다. 실제 secret 값은 읽지도 출력하지도 않는다.
훅 스크립트는 OS 레벨에서 파일을 읽으므로 `.env.example` 가 Read 도구 권한으로
차단되어 있어도 동작한다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def project_root() -> Path:
    """프로젝트 루트를 찾는다. 훅 실행 환경에서는 CLAUDE_PROJECT_DIR 를 우선 사용한다."""
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    return Path(__file__).resolve().parents[1]


ROOT = project_root()
CONFIG_PY = ROOT / "backend" / "app" / "core" / "config.py"
ENV_EXAMPLE = ROOT / ".env.example"

# config.py 의 Settings 필드가 아니지만 .env.example 에 의도적으로 존재하는 변수.
# - VITE_*: frontend 전용 public 값(Vite 가 빌드 시 읽음, backend Settings 가 아님)
# - POSTGRES_USER/PASSWORD/DB/PORT: docker-compose.yml 이 직접 읽는 로컬 DB 초기화 값
NON_SETTINGS_ENV_VARS = {
    "VITE_API_BASE_URL",
    "VITE_GOOGLE_CLIENT_ID",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_PORT",
}

# 편집 시 검사를 트리거하는 소스 파일(이 둘이 환경변수의 진실 소스).
DOC_SET = [
    ".env.example",
    "ENVIRONMENT_VARIABLE_SETUP.md",
    "ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md",
    "docs/harness/features/deployment-runtime.md",
]


def parse_settings_fields(text: str) -> set[str]:
    """Settings 클래스 본문에서 환경변수 필드 이름을 추출한다."""
    fields: set[str] = set()
    in_settings = False
    for line in text.splitlines():
        if re.match(r"^class\s+Settings\b", line):
            in_settings = True
            continue
        if in_settings and re.match(r"^class\s+\w", line):
            break
        if not in_settings:
            continue
        # 클래스 본문에서 4칸 들여쓰기 + 대문자 시작 + ':' 형태의 필드 선언.
        # PrivateAttr 의 _database_url_source 같은 밑줄 시작 필드는 제외된다.
        m = re.match(r"^    ([A-Z][A-Z0-9_]*)\s*:", line)
        if m:
            fields.add(m.group(1))
    return fields


def parse_env_vars(text: str) -> set[str]:
    """.env.example 에 등장하는 변수 이름을 추출한다.

    - `NAME=...` 할당
    - `# NAME=...` 주석 처리된 preset
    - `# - NAME` 상단 체크리스트
    """
    names: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        # 체크리스트: "# - NAME"
        m = re.match(r"^#\s*-\s*([A-Z][A-Z0-9_]*)\s*$", line)
        if m:
            names.add(m.group(1))
            continue
        # 할당 또는 주석 preset: "NAME=" / "# NAME="
        m = re.match(r"^#?\s*([A-Z][A-Z0-9_]*)\s*=", line)
        if m:
            names.add(m.group(1))
    return names


def compute_drift() -> tuple[list[str], list[str]]:
    config_text = CONFIG_PY.read_text(encoding="utf-8")
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    settings_fields = parse_settings_fields(config_text)
    env_vars = parse_env_vars(env_text)

    missing_in_env = sorted(settings_fields - env_vars)
    orphan_in_env = sorted(env_vars - settings_fields - NON_SETTINGS_ENV_VARS)
    return missing_in_env, orphan_in_env


def is_trigger(path: str) -> bool:
    """편집된 파일이 환경변수 진실 소스인지 판정한다."""
    norm = Path(path).as_posix()
    if norm.endswith("backend/app/core/config.py"):
        return True
    if Path(path).name in {".env.example", ".env_example"}:
        return True
    return False


def edited_path_from_stdin() -> str | None:
    data = sys.stdin.read()
    if not data.strip():
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def report(missing: list[str], orphan: list[str]) -> str:
    lines = ["환경변수 문서 동기화 점검: config.py 와 .env.example 사이에 드리프트가 있습니다."]
    if missing:
        lines.append("")
        lines.append("config.py(Settings)에는 있으나 .env.example 에 없는 변수(추가 필요):")
        lines.extend(f"  - {n}" for n in missing)
    if orphan:
        lines.append("")
        lines.append(".env.example 에는 있으나 config.py(Settings)에 없는 변수(삭제/오타/허용목록 확인):")
        lines.extend(f"  - {n}" for n in orphan)
    lines.append("")
    lines.append("아래 환경변수 문서를 함께 최신화하세요(AGENTS.md §18):")
    lines.extend(f"  - {d}" for d in DOC_SET)
    lines.append("문서에는 실제 값을 적지 말고 변수 이름/용도/공개여부/기본값만 기록합니다.")
    return "\n".join(lines)


def main() -> int:
    # Windows 콘솔/파이프 기본 인코딩(cp949 등)에서 한국어가 깨지지 않도록 UTF-8 강제.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    manual = "--check" in sys.argv[1:]

    if not CONFIG_PY.exists() or not ENV_EXAMPLE.exists():
        # 소스를 못 찾으면 조용히 통과(잘못된 위치에서 호출된 경우 훅을 방해하지 않는다).
        if manual:
            print("환경변수 소스를 찾지 못했습니다: config.py 또는 .env.example 경로를 확인하세요.")
            return 1
        return 0

    if not manual:
        edited = edited_path_from_stdin()
        if edited is None or not is_trigger(edited):
            return 0

    missing, orphan = compute_drift()
    if not missing and not orphan:
        if manual:
            print("환경변수 문서 동기화 OK: config.py 와 .env.example 변수 목록이 일치합니다.")
        return 0

    msg = report(missing, orphan)
    if manual:
        print(msg)
        return 1
    # PostToolUse 훅: exit 2 -> stderr 가 에이전트에게 피드백된다(편집은 유지).
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

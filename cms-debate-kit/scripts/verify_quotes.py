#!/usr/bin/env python3
"""Verify numbered evidence quotations in a CMS debate log.

Usage:
    python verify_quotes.py <excerpt.md> <debate-log.txt> <report.md>
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path


EVIDENCE_LINE = re.compile(
    r"^\s*2\.\s*근거\s*원문\s*[:：]\s*\[(\d+)\]\s*(.+?)\s*$"
)
PARAGRAPH = re.compile(
    r"^\s*\[(\d+)\]\s*(.*?)(?=^\s*\[\d+\]\s*|\Z)", re.MULTILINE | re.DOTALL
)
QUOTE_PAIRS = (("“", "”"), ('"', '"'), ("‘", "’"), ("'", "'"))


def remove_outer_quotes(text: str) -> str:
    value = text.strip()
    for opening, closing in QUOTE_PAIRS:
        if value.startswith(opening) and value.endswith(closing):
            return value[len(opening) : -len(closing)].strip()
    return value


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_paragraphs(source: str) -> dict[str, str]:
    return {number: body.strip() for number, body in PARAGRAPH.findall(source)}


def extract_evidence(log: str) -> list[tuple[str, str]]:
    found = []
    for line in log.splitlines():
        match = EVIDENCE_LINE.match(line)
        if match:
            found.append((match.group(1), remove_outer_quotes(match.group(2))))
    return found


def escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def nearest_ratio(quote: str, paragraphs: dict[str, str]) -> tuple[float, str]:
    best_ratio, best_number = 0.0, ""
    for number, body in paragraphs.items():
        ratio = difflib.SequenceMatcher(None, normalize(quote), normalize(body)).ratio()
        if ratio > best_ratio:
            best_ratio, best_number = ratio, number
    return best_ratio, best_number


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2

    source_path, log_path, report_path = map(Path, sys.argv[1:])
    source = source_path.read_text(encoding="utf-8")
    log = log_path.read_text(encoding="utf-8")
    paragraphs = parse_paragraphs(source)
    evidence = extract_evidence(log)

    rows = []
    counts = {"✔": 0, "△": 0, "✖": 0}
    for index, (number, quote) in enumerate(evidence, 1):
        cited = paragraphs.get(number)
        if cited is not None and quote in cited:
            mark, note = "✔", "원문과 문단 번호 일치"
        else:
            other = next((n for n, body in paragraphs.items() if quote in body), None)
            if other:
                mark, note = "△", f"인용문은 있으나 실제 문단은 [{other}]"
            elif cited is None:
                mark, note = "✖", f"문단 [{number}]을 발췌문에서 확인 불가"
            else:
                ratio, nearest = nearest_ratio(quote, paragraphs)
                mark = "△" if ratio >= 0.80 else "✖"
                note = f"원문 그대로 일치하지 않음; 최근접 [{nearest}] {ratio:.0%}"
        counts[mark] += 1
        rows.append(
            f"| {index} | [{number}] | {escape_cell(quote[:70])} | {mark} | {escape_cell(note)} |"
        )

    lines = [
        "# 인용 검증리포트",
        "",
        f"- 발췌문: `{source_path.name}`",
        f"- 토론 로그: `{log_path.name}`",
        f"- 검사 {len(evidence)}건 — ✔ 일치 {counts['✔']} / △ 확인 필요 {counts['△']} / ✖ 불일치 {counts['✖']}",
        "",
        "| # | 문단 | 인용문 | 판정 | 비고 |",
        "|---|---|---|---|---|",
        *rows,
    ]
    if not evidence:
        lines.extend(["", "> 문단 번호가 붙은 `2. 근거 원문:` 발언을 찾지 못했습니다."])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"검증 완료: {len(evidence)}건 -> {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


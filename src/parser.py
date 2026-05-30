"""議事録テキストのパース処理."""

import re


def _parse_lines(lines: list[str]) -> list[dict]:
    """行リストをパースして構造化データに変換する."""
    result = []
    current_speaker = None

    for raw_line in lines:
        line = raw_line.rstrip("\n\r")

        if not line.strip():
            continue

        if line.strip().startswith("#"):
            continue

        if line.strip() == "---":
            result.append({"speaker": "", "text": "", "type": "section_break"})
            continue

        match = re.match(r"^(.+?)[:\uff1a](.+)$", line)
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
            current_speaker = speaker
            result.append({"speaker": speaker, "text": text, "type": "line"})
        else:
            if current_speaker:
                result.append({"speaker": current_speaker, "text": line.strip(), "type": "line"})

    return result


def parse_transcript(filepath: str) -> list[dict]:
    """議事録テキストファイルをパースして構造化データに変換する."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    return _parse_lines(lines)


def parse_text(text: str) -> list[dict]:
    """議事録テキスト文字列を直接パースして構造化データに変換する."""
    lines = text.splitlines()
    return _parse_lines(lines)

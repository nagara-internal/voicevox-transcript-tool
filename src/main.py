"""CLIエントリーポイント."""

import argparse
import logging
import os
import sys
import tempfile

from tqdm import tqdm

from config_loader import load_config, get_speaker_config
from parser import parse_transcript, parse_text
from synthesizer import VoicevoxSynthesizer
from audio_combiner import combine_wav_segments, convert_to_mp3, get_wav_duration

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def list_speakers(synthesizer: VoicevoxSynthesizer) -> None:
    """VOICEVOXで利用可能な話者一覧を表示する."""
    speakers = synthesizer.get_speakers()
    print("\n📢 利用可能な話者一覧:\n")
    for speaker in speakers:
        name = speaker["name"]
        for style in speaker.get("styles", []):
            style_name = style["name"]
            sid = style["id"]
            print(f"  ID: {sid:3d}  |  {name} ({style_name})")
    print()


def dry_run(entries: list[dict], config: dict) -> None:
    """パース結果と話者マッピングを表示する（音声合成はしない）."""
    print("\n📝 パース結果:\n")
    speaker_set = set()

    for i, entry in enumerate(entries):
        if entry["type"] == "section_break":
            print(f"  [{i+1:3d}] --- セクション区切り ---")
        else:
            speaker = entry["speaker"]
            text = entry["text"]
            speaker_set.add(speaker)
            sc = get_speaker_config(config, speaker)
            mapped = speaker in config.get("speakers", {})
            marker = "✅" if mapped else "⚠️"
            print(f"  [{i+1:3d}] {marker} {speaker} (ID:{sc['speaker_id']}): {text[:60]}{'...' if len(text) > 60 else ''}")

    print(f"\n📊 合計: {len(entries)} エントリ")
    print(f"   話者: {len(speaker_set)} 名 ({', '.join(sorted(speaker_set))})")

    unmapped = [s for s in speaker_set if s not in config.get("speakers", {})]
    if unmapped:
        print(f"\n⚠ 以下の話者はconfig.yamlにマッピングがありません（デフォルト話者を使用）:")
        for s in unmapped:
            print(f"   - {s}")
    print()


def format_duration(seconds: float) -> str:
    """秒を 時:分:秒 形式に変換する."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}時間{minutes}分{secs}秒"
    return f"{minutes}分{secs}秒"


def format_filesize(size_bytes: int) -> str:
    """バイト数を読みやすい形式に変換する."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_entries(args) -> list[dict]:
    """入力ソース（ファイル / -t テキスト / stdin）からエントリを取得する."""
    # 1. -t でテキスト直接指定
    if args.text:
        return parse_text(args.text)

    # 2. stdin からパイプ入力
    if not sys.stdin.isatty() and not args.input:
        stdin_text = sys.stdin.read()
        if stdin_text.strip():
            return parse_text(stdin_text)

    # 3. ファイルパス指定
    if args.input:
        if not os.path.exists(args.input):
            print(f"❌ ファイルが見つかりません: {args.input}")
            sys.exit(1)
        return parse_transcript(args.input)

    return []


def synthesize_entries(entries: list[dict], synthesizer: VoicevoxSynthesizer, config: dict) -> tuple[list[dict], int]:
    """エントリを音声合成してセグメントリストを返す."""
    segments = []
    failed_count = 0

    for entry in tqdm(entries, desc="合成中", unit="行"):
        if entry["type"] == "section_break":
            segments.append({"wav_data": [], "type": "section_break"})
            continue

        speaker = entry["speaker"]
        text = entry["text"]
        sc = get_speaker_config(config, speaker)

        try:
            wav_parts = synthesizer.synthesize_long_text(
                text=text,
                speaker_id=sc["speaker_id"],
                speed_scale=sc.get("speed_scale", 1.0),
                pitch_scale=sc.get("pitch_scale", 0.0),
            )
            segments.append({"wav_data": wav_parts, "type": "line"})
        except Exception as e:
            logger.warning(f"合成失敗 (スキップ) [{speaker}]: {text[:40]}... -> {e}")
            failed_count += 1

    return segments, failed_count


def export_audio(segments: list[dict], output_path: str, audio_config: dict) -> str:
    """セグメントを結合してファイルに出力する。最終ファイルパスを返す."""
    output_format = audio_config.get("output_format", "mp3")
    wav_output = output_path.rsplit(".", 1)[0] + ".wav"

    print(f"\n🔗 音声ファイルを結合中...")

    combine_wav_segments(
        segments=segments,
        output_path=wav_output,
        silence_between_lines=audio_config["silence_between_lines"],
        silence_between_sections=audio_config["silence_between_sections"],
        sample_rate=audio_config["sample_rate"],
    )

    final_output = wav_output
    if output_format == "mp3":
        mp3_output = output_path.rsplit(".", 1)[0] + ".mp3"
        if convert_to_mp3(wav_output, mp3_output, audio_config.get("mp3_quality", 2)):
            os.remove(wav_output)
            final_output = mp3_output

    return final_output


def main():
    parser = argparse.ArgumentParser(
        description="議事録テキストからVOICEVOXで音声ファイルを生成するツール",
        epilog="""使用例:
  python src/main.py transcript.txt                    # ファイルから生成
  python src/main.py -t '施設長: こんにちは'            # テキスト直接指定
  echo '施設長: こんにちは' | python src/main.py        # パイプで渡す
  cat transcript.txt | python src/main.py -o out.mp3   # パイプ + 出力先指定
  python src/main.py --list-speakers                   # 話者一覧""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="?", help="議事録テキストファイルのパス")
    parser.add_argument("-t", "--text", help="議事録テキストを直接指定（ファイル不要）")
    parser.add_argument("-o", "--output", default=None, help="出力ファイルパス（デフォルト: output/meeting_audio.mp3）")
    parser.add_argument("-c", "--config", default="config.yaml", help="config.yamlのパス")
    parser.add_argument("--list-speakers", action="store_true", help="利用可能な話者一覧を表示して終了")
    parser.add_argument("--dry-run", action="store_true", help="音声合成せずにパース結果と話者マッピングを表示")
    args = parser.parse_args()

    # config読み込み
    config = load_config(args.config)
    vv_config = config["voicevox"]
    audio_config = config["audio"]

    # dry-run
    if args.dry_run:
        entries = get_entries(args)
        if not entries:
            print("❌ 入力がありません。ファイルパス、-t テキスト、またはパイプで議事録を渡してください。")
            sys.exit(1)
        dry_run(entries, config)
        sys.exit(0)

    # VOICEVOX接続確認
    synthesizer = VoicevoxSynthesizer(
        base_url=vv_config["base_url"],
        timeout=vv_config["timeout"],
    )

    if not synthesizer.check_connection():
        print("❌ VOICEVOXが起動していません。")
        print(f"   接続先: {vv_config['base_url']}")
        print(f"   起動方法: docker run -d --rm --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-latest")
        sys.exit(1)

    # --list-speakers
    if args.list_speakers:
        list_speakers(synthesizer)
        sys.exit(0)

    # 入力取得
    entries = get_entries(args)
    if not entries:
        print("❌ 入力がありません。以下のいずれかの方法で議事録を渡してください：")
        print("   python src/main.py transcript.txt          # ファイル")
        print("   python src/main.py -t '施設長: こんにちは'   # テキスト直接")
        print("   echo '施設長: こんにちは' | python src/main.py  # パイプ")
        sys.exit(1)

    # 出力パス決定
    output_format = audio_config.get("output_format", "mp3")
    output_path = args.output or f"output/meeting_audio.{output_format}"

    # 音声合成
    print(f"\n🎙 音声合成を開始します（{len(entries)} エントリ）...\n")

    segments, failed_count = synthesize_entries(entries, synthesizer, config)

    if not any(s["type"] == "line" for s in segments):
        print("❌ 音声を1つも生成できませんでした。")
        sys.exit(1)

    # 出力
    final_output = export_audio(segments, output_path, audio_config)

    # 完了メッセージ
    file_size = os.path.getsize(final_output)
    duration = get_wav_duration(final_output) if final_output.endswith(".wav") else None

    print(f"\n✅ 音声ファイルの生成が完了しました！")
    print(f"   📁 出力先: {final_output}")
    print(f"   📦 ファイルサイズ: {format_filesize(file_size)}")
    if duration is not None:
        print(f"   ⏱ 推定再生時間: {format_duration(duration)}")
    if failed_count > 0:
        print(f"   ⚠ 合成失敗: {failed_count} 行（スキップ済み）")
    print()


if __name__ == "__main__":
    main()

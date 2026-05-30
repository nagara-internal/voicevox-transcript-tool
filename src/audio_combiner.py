"""WAVファイル結合・MP3変換."""

import io
import os
import struct
import subprocess
import shutil
import wave
import numpy as np


def generate_silence(duration_sec: float, sample_rate: int = 24000) -> bytes:
    """指定秒数の無音WAVバイナリを生成する."""
    num_samples = int(sample_rate * duration_sec)
    silence = np.zeros(num_samples, dtype=np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(silence.tobytes())

    return buf.getvalue()


def _read_wav_frames(wav_bytes: bytes) -> tuple[bytes, dict]:
    """WAVバイナリからフレームデータとパラメータを読み取る."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        params = {
            "nchannels": wf.getnchannels(),
            "sampwidth": wf.getsampwidth(),
            "framerate": wf.getframerate(),
        }
        frames = wf.readframes(wf.getnframes())
    return frames, params


def combine_wav_segments(
    segments: list[dict],
    output_path: str,
    silence_between_lines: float = 0.8,
    silence_between_sections: float = 2.0,
    sample_rate: int = 24000,
) -> None:
    """複数のWAVセグメントを結合して1つのWAVファイルに書き出す.

    segments: [{"wav_data": list[bytes], "type": "line" | "section_break"}, ...]
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    line_silence = generate_silence(silence_between_lines, sample_rate)
    section_silence = generate_silence(silence_between_sections, sample_rate)

    all_frames = bytearray()
    params = None

    for i, segment in enumerate(segments):
        if segment["type"] == "section_break":
            section_frames, _ = _read_wav_frames(section_silence)
            all_frames.extend(section_frames)
            continue

        wav_parts = segment.get("wav_data", [])
        for wav_bytes in wav_parts:
            frames, p = _read_wav_frames(wav_bytes)
            if params is None:
                params = p
            all_frames.extend(frames)

        # 発言間に無音を挿入（最後の要素以外）
        if i < len(segments) - 1:
            silence_frames, _ = _read_wav_frames(line_silence)
            all_frames.extend(silence_frames)

    if params is None:
        params = {"nchannels": 1, "sampwidth": 2, "framerate": sample_rate}

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(params["nchannels"])
        wf.setsampwidth(params["sampwidth"])
        wf.setframerate(params["framerate"])
        wf.writeframes(bytes(all_frames))


def convert_to_mp3(wav_path: str, mp3_path: str, quality: int = 2) -> bool:
    """ffmpegでWAV→MP3変換する。成功したらTrue、失敗したらFalseを返す."""
    if not shutil.which("ffmpeg"):
        print("⚠ ffmpegが見つかりません。WAV形式のまま出力します。")
        print("  MP3に変換するにはffmpegをインストールしてください:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        return False

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_path,
                "-qscale:a", str(quality),
                mp3_path,
            ],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠ MP3変換に失敗しました: {e.stderr.decode()}")
        return False


def get_wav_duration(wav_path: str) -> float:
    """WAVファイルの再生時間（秒）を取得する."""
    with wave.open(wav_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / rate

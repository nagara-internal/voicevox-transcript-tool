"""VOICEVOX API呼び出し・音声合成."""

import time
import logging
import requests

logger = logging.getLogger(__name__)


class VoicevoxSynthesizer:
    """VOICEVOX APIを使った音声合成クライアント."""

    def __init__(self, base_url: str = "http://localhost:50021", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = 3
        self.retry_interval = 1.0

    def check_connection(self) -> bool:
        """VOICEVOXへの接続を確認する."""
        try:
            resp = requests.get(f"{self.base_url}/version", timeout=5)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    def get_speakers(self) -> list[dict]:
        """利用可能な話者一覧を取得する."""
        resp = requests.get(f"{self.base_url}/speakers", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def synthesize(
        self,
        text: str,
        speaker_id: int,
        speed_scale: float = 1.0,
        pitch_scale: float = 0.0,
    ) -> bytes:
        """テキストを音声合成してWAVバイナリを返す."""
        for attempt in range(self.max_retries):
            try:
                return self._synthesize_once(text, speaker_id, speed_scale, pitch_scale)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"合成リトライ ({attempt + 1}/{self.max_retries}): {e}")
                    time.sleep(self.retry_interval)
                else:
                    raise

    def _synthesize_once(
        self,
        text: str,
        speaker_id: int,
        speed_scale: float,
        pitch_scale: float,
    ) -> bytes:
        # Step 1: audio_query
        query_resp = requests.post(
            f"{self.base_url}/audio_query",
            params={"text": text, "speaker": speaker_id},
            timeout=self.timeout,
        )
        query_resp.raise_for_status()
        query = query_resp.json()

        # パラメータを上書き
        query["speedScale"] = speed_scale
        query["pitchScale"] = pitch_scale

        # Step 2: synthesis
        synth_resp = requests.post(
            f"{self.base_url}/synthesis",
            params={"speaker": speaker_id},
            json=query,
            timeout=self.timeout,
        )
        synth_resp.raise_for_status()

        return synth_resp.content

    def synthesize_long_text(
        self,
        text: str,
        speaker_id: int,
        speed_scale: float = 1.0,
        pitch_scale: float = 0.0,
    ) -> list[bytes]:
        """長いテキストを句点で分割して合成する。200文字超の場合に分割."""
        if len(text) <= 200:
            return [self.synthesize(text, speaker_id, speed_scale, pitch_scale)]

        # 句点で分割
        segments = []
        for part in text.split("。"):
            part = part.strip()
            if part:
                segments.append(part + "。")

        wav_parts = []
        for segment in segments:
            wav_data = self.synthesize(segment, speaker_id, speed_scale, pitch_scale)
            wav_parts.append(wav_data)

        return wav_parts

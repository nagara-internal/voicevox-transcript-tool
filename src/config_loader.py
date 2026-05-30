"""config.yaml の読み込みとデフォルト値の提供."""

import os
import yaml


DEFAULT_CONFIG = {
    "voicevox": {
        "base_url": "http://localhost:50021",
        "timeout": 30,
    },
    "speakers": {},
    "default_speaker": {
        "speaker_id": 3,
        "speed_scale": 1.0,
        "pitch_scale": 0.0,
    },
    "audio": {
        "silence_between_lines": 0.8,
        "silence_between_sections": 2.0,
        "sample_rate": 24000,
        "output_format": "mp3",
        "mp3_quality": 2,
    },
}


def load_config(config_path: str) -> dict:
    """config.yaml を読み込む。存在しない場合はデフォルト設定を返す."""
    if not os.path.exists(config_path):
        print(f"⚠ 設定ファイル '{config_path}' が見つかりません。デフォルト設定で動作します。")
        return DEFAULT_CONFIG

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    config = DEFAULT_CONFIG.copy()
    for key in DEFAULT_CONFIG:
        if key in user_config:
            if isinstance(DEFAULT_CONFIG[key], dict):
                config[key] = {**DEFAULT_CONFIG[key], **user_config[key]}
            else:
                config[key] = user_config[key]

    return config


def get_speaker_config(config: dict, speaker_name: str) -> dict:
    """話者名からVOICEVOX設定を取得する。マッピングにない場合はデフォルトを返す."""
    speakers = config.get("speakers", {})
    if speaker_name in speakers:
        return speakers[speaker_name]
    return config.get("default_speaker", DEFAULT_CONFIG["default_speaker"])

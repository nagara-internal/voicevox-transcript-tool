# 議事録→音声変換ツール（VOICEVOX API利用）

介護会議の議事録テキストから、VOICEVOXを使ってデモ用音声ファイル（MP3/WAV）を自動生成するCLIツールです。

## 前提条件

- **Python 3.10以上**
- **VOICEVOX** がインストール・起動済みであること（[ダウンロード](https://voicevox.hiroshiba.jp/)）
- **ffmpeg** がインストール済みであること（MP3変換に必要。WAV出力のみの場合は不要）

## セットアップ

```bash
cd voicevox-transcript-tool

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 使い方

### 1. VOICEVOXを起動する

VOICEVOXアプリを起動してください。APIが `http://localhost:50021` で自動的に稼働します。

### 2. 基本的な使い方

```bash
# サンプル議事録から音声を生成
python src/main.py samples/sample_transcript.txt

# 出力先を指定
python src/main.py samples/sample_transcript.txt -o output/demo_meeting.mp3

# 設定ファイルを指定
python src/main.py samples/sample_transcript.txt -c my_config.yaml
```

### 3. 話者一覧の確認

VOICEVOXで使用可能な話者とIDを確認できます。

```bash
python src/main.py --list-speakers
```

出力例:
```
📢 利用可能な話者一覧:

  ID:   0  |  四国めたん (ノーマル)
  ID:   2  |  四国めたん (あまあま)
  ID:   3  |  ずんだもん (ノーマル)
  ...
```

### 4. パース結果の確認（dry-run）

音声合成を行わず、議事録のパース結果と話者マッピングの状態だけを確認できます。

```bash
python src/main.py samples/sample_transcript.txt --dry-run
```

出力例:
```
📝 パース結果:

  [  1] ✅ 施設長 (ID:3): 本日はお忙しいところお集まりいただきありがとうございます。それでは...
  [  2] ✅ ケアマネ (ID:2): よろしくお願いいたします。まず、前回の会議からの経過を共有させて...
  ...

📊 合計: 45 エントリ
   話者: 5 名 (ケアマネ, 介護士A, 介護士B, 施設長, 看護師)
```

## 議事録の書き方

テキストファイルに `話者名: 発言内容` の形式で記載します。

```text
施設長: 本日はお集まりいただきありがとうございます。
ケアマネ：よろしくお願いいたします。
介護士A: 先月の様子についてご報告します。
```

### ルール

| 記法 | 意味 |
|------|------|
| `話者名: テキスト` | 発言（半角コロン区切り） |
| `話者名：テキスト` | 発言（全角コロン区切り） |
| `---` | セクション区切り（長めの無音を挿入） |
| `# コメント` | コメント行（スキップ） |
| 空行 | スキップ |
| コロンなしの行 | 直前の話者の発言の続き |

## 設定ファイル（config.yaml）

`config.yaml` で話者とVOICEVOXの音声IDのマッピングを設定します。

```yaml
speakers:
  施設長:
    speaker_id: 3      # VOICEVOXの話者ID
    speed_scale: 1.0    # 話速（1.0が標準）
    pitch_scale: 0.0    # ピッチ（0.0が標準）
  ケアマネ:
    speaker_id: 2
    speed_scale: 1.0
    pitch_scale: 0.0
```

マッピングにない話者名が出てきた場合は `default_speaker` の設定が使用されます。

## コマンドオプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `input` | 議事録テキストファイルのパス（必須） | - |
| `-o`, `--output` | 出力ファイルパス | `output/meeting_audio.mp3` |
| `-c`, `--config` | config.yamlのパス | `config.yaml` |
| `--list-speakers` | 利用可能な話者一覧を表示して終了 | - |
| `--dry-run` | 音声合成せずにパース結果を表示 | - |

## 注意事項

- VOICEVOXのCPUモードでは1行あたり数秒かかります。数百行の議事録だと生成に数十分かかる場合があります。
- 200文字を超える長い発言は、句点（。）で自動分割してから合成されます。

## クレジット

本ツールは [VOICEVOX](https://voicevox.hiroshiba.jp/) の音声合成エンジンを使用しています。
生成した音声ファイルを利用する際は、使用したキャラクターに応じて以下のクレジット表記が必要です。

```
VOICEVOX:ずんだもん、VOICEVOX:四国めたん（使用キャラクター名）
```

各キャラクターの利用規約は [VOICEVOX公式サイト](https://voicevox.hiroshiba.jp/) をご確認ください。

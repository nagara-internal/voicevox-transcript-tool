# text-to-mp3 音声変換ツール

議事録テキスト（`話者名: 発言内容` 形式）を、VOICEVOXのキャラクター音声（ずんだもん・四国めたんなど）でMP3に変換するツールです。

**導入ガイド（社員向け）:** https://nagara-internal.github.io/voicevox-transcript-tool/

---

## 社員の方向け（はじめてお使いの方）

### 必要なもの

- **Mac**（macOS）
- **VOICEVOXアプリ**（無料。初回のみダウンロードが必要）
- インターネット接続（初回セットアップ時のみ）

---

### 手順

#### ① ツールのファイルをダウンロードする

管理者からZIPファイルを受け取り、ダブルクリックで解凍してください。

> GitHubにアクセスできる場合は、ページ右上の **「Code」→「Download ZIP」** からダウンロードできます。

解凍するとフォルダが作成されます。このフォルダは**消さずに**どこか分かりやすい場所（例：書類フォルダ）に置いておいてください。

---

#### ② セットアップする（初回のみ・1回だけ）

解凍したフォルダの中に **「setup.command」** というファイルがあります。

**ダブルクリックしてください。**

> 「開発元が未確認のため開けません」と表示された場合：  
> **右クリック（または Control+クリック）→「開く」→「開く」** を選んでください。

黒い画面（ターミナル）が自動で開き、セットアップが始まります。  
「セットアップ完了！」と表示されたら **Enterキーを押して閉じてください。**

セットアップ完了後、**デスクトップに「VOICEVOX変換ツール」が自動で作成されます。**

---

#### ③ VOICEVOXアプリをインストールする（初回のみ）

[https://voicevox.hiroshiba.jp/](https://voicevox.hiroshiba.jp/) にアクセスして、VOICEVOXアプリをダウンロード・インストールしてください。

インストール後、アプリを起動しておけばOKです。

---

#### ④ 毎回の使い方

1. **VOICEVOXアプリを起動する**
2. **デスクトップの「VOICEVOX変換ツール」をダブルクリックする**
3. ブラウザが自動で開きます

あとは画面の指示に沿って、議事録テキストを貼り付けて「変換」を押すだけです。

---

### 使い方（ブラウザ画面）

| ステップ | 操作 |
|---------|------|
| STEP 1 | 議事録テキストを貼り付けて「解析する」を押す |
| STEP 2 | 話者ごとにキャラクターを選ぶ |
| STEP 3 | MP3ファイルをダウンロードする |

---

### トラブルシューティング（社員向け）

**「VOICEVOX に接続できません」と表示される**  
→ VOICEVOXアプリが起動していません。VOICEVOXを起動してから、ブラウザをリロードしてください。

**ブラウザが開かない**  
→ デスクトップの「VOICEVOX変換ツール」をダブルクリックしてください。  
　 それでも開かない場合は担当者に連絡してください。

**「開発元が未確認」と出てファイルが開けない**  
→ 右クリック（または Control+クリック）→「開く」→「開く」を選んでください。

---
---

## 開発者向け

### 概要

CLIツールとして、または Streamlit UIとして使用できます。

### セットアップ

```bash
git clone git@github.com:nagara-internal/voicevox-transcript-tool.git
cd voicevox-transcript-tool
bash install.sh   # または setup.command をダブルクリック
```

### UIの起動（開発時）

```bash
bash launcher.sh
```

または：

```bash
.venv/bin/streamlit run app.py
```

### CLIとして実行

#### VOICEVOXを起動する

```bash
# macOSアプリ版: アプリを起動するだけでOK

# Docker版
docker run -d --rm --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-latest
```

#### 変換を実行する

```bash
# generate.sh を使う（推奨）
./generate.sh samples/my_meeting.txt

# python で直接実行
python src/main.py samples/my_meeting.txt -o output/demo.mp3

# dry-run（音声合成せずパース結果を確認）
python src/main.py samples/my_meeting.txt --dry-run

# 話者一覧を確認
python src/main.py --list-speakers
```

### 議事録テキストの書き方

```text
# コメント行（#で始まる行）はスキップ

施設長: 本日はお集まりいただきありがとうございます。
ケアマネ：よろしくお願いします。
介護士A: 先月の報告をします。
前回から体調が安定しています。  # ← コロンなしの行は直前の話者の続き

---  # ← セクション区切り（前後に2秒の無音）

施設長: では次の議題に移ります。
```

### config.yaml の設定

```yaml
voicevox:
  base_url: "http://localhost:50021"

speakers:
  施設長:
    speaker_id: 3      # ずんだもん（ノーマル）
    speed_scale: 1.0
    pitch_scale: 0.0
  ケアマネ:
    speaker_id: 2      # 四国めたん（あまあま）
    speed_scale: 1.0
    pitch_scale: 0.0

default_speaker:
  speaker_id: 3
  speed_scale: 1.0
  pitch_scale: 0.0

audio:
  silence_between_lines: 0.8
  silence_between_sections: 2.0
  output_format: "mp3"
```

### よく使うキャラクターID

| ID | キャラクター | スタイル |
|----|-------------|---------|
| 3  | ずんだもん | ノーマル |
| 1  | ずんだもん | あまあま |
| 0  | 四国めたん | ノーマル |
| 2  | 四国めたん | あまあま |
| 8  | 春日部つむぎ | ノーマル |
| 10 | 雨晴はう | ノーマル |
| 13 | 青山龍星 | ノーマル |

### ディレクトリ構成

```
voicevox-transcript-tool/
├── app.py                 # Streamlit UI
├── setup.command          # セットアップ（ダブルクリック用）
├── install.sh             # セットアップ（CLI用、同じ内容）
├── launcher.sh            # 開発者向け起動ショートカット
├── config.yaml            # 話者マッピング設定
├── requirements.txt       # Pythonパッケージ
├── samples/               # 議事録テキストのサンプル
├── output/                # 生成MP3の出力先（.gitignore）
└── src/
    ├── main.py            # CLIエントリーポイント
    ├── parser.py          # テキストパース
    ├── synthesizer.py     # VOICEVOX APIクライアント
    ├── audio_combiner.py  # WAV結合・MP3変換
    └── config_loader.py   # config.yaml 読み込み
```

### CLIオプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `input` | 議事録テキストファイルのパス | - |
| `-t`, `--text` | テキストを直接指定 | - |
| `-o`, `--output` | 出力ファイルパス | `output/meeting_audio.mp3` |
| `-c`, `--config` | config.yaml のパス | `config.yaml` |
| `--list-speakers` | 話者一覧を表示して終了 | - |
| `--dry-run` | パース結果のみ表示（合成しない） | - |

---

## クレジット

本ツールは [VOICEVOX](https://voicevox.hiroshiba.jp/) の音声合成エンジンを使用しています。  
生成した音声ファイルを利用する際は、使用したキャラクターのクレジット表記が必要です。

```
VOICEVOX:ずんだもん
VOICEVOX:四国めたん
```

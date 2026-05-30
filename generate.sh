#!/bin/bash
# 議事録→音声変換 ショートカット
# 使い方:
#   ./generate.sh transcript.txt                     # ファイルから
#   ./generate.sh -t '施設長: こんにちは'              # テキスト直接
#   echo '施設長: テスト' | ./generate.sh             # パイプ
#   ./generate.sh transcript.txt -o output/demo.mp3  # 出力先指定

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# VOICEVOXが起動してなければDockerで自動起動
if ! curl -s http://localhost:50021/version > /dev/null 2>&1; then
    echo "🐳 VOICEVOXを起動中..."
    docker run -d --rm --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-latest > /dev/null 2>&1
    # 起動待ち
    for i in $(seq 1 30); do
        if curl -s http://localhost:50021/version > /dev/null 2>&1; then
            echo "✅ VOICEVOX起動完了"
            break
        fi
        sleep 1
    done
fi

python src/main.py "$@"

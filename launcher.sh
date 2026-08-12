#!/bin/bash
# launcher.sh — 開発者向け起動スクリプト（install.sh 実行後に使用）

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "❌ .venv が見つかりません。先に install.sh を実行してください。"
    exit 1
fi

.venv/bin/streamlit run app.py --browser.gatherUsageStats false

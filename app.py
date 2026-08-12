"""ながらかいご 音声変換 — Streamlit ローカル UI."""

import os
import sys
import shutil
import tempfile

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from parser import parse_text
from synthesizer import VoicevoxSynthesizer
from audio_combiner import combine_wav_segments, convert_to_mp3
from config_loader import load_config

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
VOICEVOX_URL = "http://localhost:50021"


# ── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ながらかいご 音声変換",
    page_icon="🎙",
    layout="centered",
)

st.markdown("""
<style>
.step-bar { display: flex; gap: 8px; margin-bottom: 1.5rem; }
.step-dot { padding: 4px 16px; border-radius: 20px; font-size: 0.85rem;
            font-weight: bold; background: #e5e7eb; color: #6b7280; }
.step-dot.active { background: #6366f1; color: white; }
.step-dot.done { background: #d1fae5; color: #065f46; }
</style>
""", unsafe_allow_html=True)


# ── キャッシュ ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=20)
def _check_voicevox() -> bool:
    return VoicevoxSynthesizer(VOICEVOX_URL).check_connection()


@st.cache_data(ttl=300)
def _get_chars() -> list[dict]:
    try:
        raw = VoicevoxSynthesizer(VOICEVOX_URL).get_speakers()
        out = []
        for spk in raw:
            for style in spk.get("styles", []):
                out.append({"label": f"{spk['name']}（{style['name']}）", "id": style["id"]})
        return out
    except Exception:
        return []


# ── session_state 初期化 ──────────────────────────────────────────────────

_DEFAULTS: dict = {
    "step": 1,
    "raw_text": "",
    "parsed_entries": None,
    "speaker_names": [],
    "speaker_map": {},
    "output_bytes": None,
    "output_filename": "output.mp3",
    "silence_lines": 0.8,
    "silence_sections": 2.0,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── ヘルパー関数 ─────────────────────────────────────────────────────────────

def _reset():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v


def _do_parse(text: str):
    """テキストを解析して STEP 2 へ進む。"""
    try:
        entries = parse_text(text)
        line_entries = [e for e in entries if e["type"] == "line"]
        if not line_entries:
            st.error("発言が見つかりませんでした。`話者名: 発言内容` の形式で記述してください。")
            return
        names = list(dict.fromkeys(e["speaker"] for e in line_entries))
        st.session_state.parsed_entries = entries
        st.session_state.speaker_names = names
        st.session_state.speaker_map = {}
        st.session_state.output_bytes = None
        st.session_state.step = 2
        st.rerun()
    except Exception as exc:
        st.error(f"解析エラー: {exc}")


def _run_synthesis(
    entries: list,
    speaker_map: dict,
    silence_lines: float,
    silence_sections: float,
):
    """合成処理を実行してダウンロード用バイト列をセッションに保存する。"""
    line_entries = [e for e in entries if e["type"] == "line"]
    total = max(len(line_entries), 1)
    config = load_config(CONFIG_PATH)
    sample_rate = config["audio"].get("sample_rate", 24000)
    mp3_quality = config["audio"].get("mp3_quality", 2)

    synth = VoicevoxSynthesizer(VOICEVOX_URL)
    progress_bar = st.progress(0.0)
    done = 0
    failed = 0

    with st.status("音声を合成中...", expanded=True) as status:
        segments = []

        for entry in entries:
            if entry["type"] == "section_break":
                segments.append({"wav_data": [], "type": "section_break"})
                st.write("— セクション区切り")
                continue

            speaker = entry["speaker"]
            text = entry["text"]
            cfg = speaker_map.get(
                speaker,
                {"speaker_id": 3, "speed_scale": 1.0, "pitch_scale": 0.0},
            )
            short = text[:60] + ("…" if len(text) > 60 else "")

            try:
                wav_parts = synth.synthesize_long_text(
                    text=text,
                    speaker_id=cfg["speaker_id"],
                    speed_scale=cfg["speed_scale"],
                    pitch_scale=cfg["pitch_scale"],
                )
                segments.append({"wav_data": wav_parts, "type": "line"})
                st.write(f"✓ **{speaker}**: {short}")
            except Exception as exc:
                failed += 1
                st.write(f"⚠ スキップ **{speaker}**: {exc}")

            done += 1
            progress_bar.progress(done / total)

        st.write("🔗 音声ファイルを結合中...")

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = os.path.join(tmpdir, "output.wav")
            mp3_path = os.path.join(tmpdir, "output.mp3")

            combine_wav_segments(
                segments=segments,
                output_path=wav_path,
                silence_between_lines=silence_lines,
                silence_between_sections=silence_sections,
                sample_rate=sample_rate,
            )

            mp3_ok = False
            if shutil.which("ffmpeg"):
                mp3_ok = convert_to_mp3(wav_path, mp3_path, mp3_quality)

            if mp3_ok:
                read_path, filename, fmt = mp3_path, "output.mp3", "MP3"
            else:
                read_path, filename, fmt = wav_path, "output.wav", "WAV（ffmpeg 未インストール）"

            with open(read_path, "rb") as f:
                audio_bytes = f.read()

        label = f"✅ 完了 — {fmt}"
        if failed:
            label = f"⚠ 完了（{failed} 件スキップ） — {fmt}"
        status.update(label=label, state="complete")

    st.session_state.output_bytes = audio_bytes
    st.session_state.output_filename = filename
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ヘッダー
# ══════════════════════════════════════════════════════════════════════════════

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🎙 ながらかいご 音声変換")
with col_status:
    voicevox_ok = _check_voicevox()
    if voicevox_ok:
        st.success("VOICEVOX 接続中", icon="✅")
    else:
        st.error("VOICEVOX 未接続", icon="❌")

if not voicevox_ok:
    with st.expander("VOICEVOXの起動方法", expanded=True):
        st.markdown("""
**VOICEVOX が起動していません。** 以下の手順で起動してください。

1. [VOICEVOX 公式サイト](https://voicevox.hiroshiba.jp/) からダウンロード・インストール
2. VOICEVOX アプリを起動（Launchpad または Applications フォルダ）
3. このページを **再読み込み**（ブラウザの更新ボタンまたは Cmd+R）
        """)
    st.stop()

st.divider()

# ── ステップバー ─────────────────────────────────────────────────────────────

step = st.session_state.step

def _sc(n: int) -> str:
    if n < step:
        return "done"
    return "active" if n == step else ""

st.markdown(f"""
<div class="step-bar">
  <span class="step-dot {_sc(1)}">STEP 1 テキスト入力</span>
  <span class="step-dot {_sc(2)}">STEP 2 話者設定</span>
  <span class="step-dot {_sc(3)}">STEP 3 音声生成</span>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — テキスト入力
# ══════════════════════════════════════════════════════════════════════════════

if step == 1:
    st.subheader("テキストを入力してください")
    st.caption("議事録テキストを貼り付けるか、.txt ファイルをアップロードしてください。")

    tab_paste, tab_file = st.tabs(["✏️ テキストを貼り付ける", "📄 ファイルをアップロード"])

    with tab_paste:
        text_input = st.text_area(
            "議事録テキスト",
            value=st.session_state.raw_text,
            height=300,
            placeholder=(
                "施設長: 本日はお集まりいただきありがとうございます。\n"
                "ケアマネ: よろしくお願いします。\n\n"
                "---\n\n"
                "施設長: では次の議題に移りましょう。\n\n"
                "# この行はコメント（読み上げをスキップ）"
            ),
            label_visibility="collapsed",
        )
        if st.button("解析する →", key="parse_paste", type="primary",
                     disabled=not text_input.strip()):
            st.session_state.raw_text = text_input
            _do_parse(text_input)

    with tab_file:
        uploaded = st.file_uploader("テキストファイル", type=["txt"],
                                    label_visibility="collapsed")
        if uploaded:
            file_text = uploaded.read().decode("utf-8", errors="replace")
            st.text_area("プレビュー", file_text, height=200, disabled=True,
                         label_visibility="collapsed")
            if st.button("解析する →", key="parse_file", type="primary"):
                st.session_state.raw_text = file_text
                _do_parse(file_text)

    with st.expander("テキストの書き方"):
        st.markdown("""
| 記法 | 説明 |
|---|---|
| `話者名: 発言内容` | 基本形式（半角・全角コロン両対応）|
| `---` | セクション区切り（無音を挿入）|
| `# テキスト` | コメント行（読み上げをスキップ）|
| コロンなし行 | 直前の話者の発言の続きとして処理 |
        """)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — 話者設定
# ══════════════════════════════════════════════════════════════════════════════

elif step == 2:
    entries = st.session_state.parsed_entries
    speakers = st.session_state.speaker_names
    chars = _get_chars()

    line_count = sum(1 for e in entries if e["type"] == "line")
    section_count = sum(1 for e in entries if e["type"] == "section_break")

    st.subheader("話者ごとのキャラクター設定")
    st.caption(
        f"解析結果: **{line_count} 発言** ／ **{section_count} セクション区切り** ／ "
        f"話者 **{len(speakers)}** 名"
    )

    if not chars:
        st.warning("VOICEVOX からキャラクター一覧を取得できませんでした。speaker_id を直接入力してください。")

    config = load_config(CONFIG_PATH)
    char_labels = [c["label"] for c in chars]
    char_ids = [c["id"] for c in chars]

    speaker_map = {}
    for speaker in speakers:
        default_cfg = config.get("speakers", {}).get(
            speaker,
            config.get("default_speaker", {"speaker_id": 3, "speed_scale": 1.0, "pitch_scale": 0.0}),
        )
        prev = st.session_state.speaker_map.get(speaker, default_cfg)

        with st.container(border=True):
            st.markdown(f"**🎤 {speaker}**")
            c1, c2, c3 = st.columns([3, 1.5, 1.5])

            with c1:
                if chars:
                    prev_id = prev.get("speaker_id", 3)
                    default_idx = char_ids.index(prev_id) if prev_id in char_ids else 0
                    selected = st.selectbox(
                        "キャラクター", char_labels, index=default_idx,
                        key=f"char_{speaker}",
                    )
                    speaker_id = char_ids[char_labels.index(selected)]
                else:
                    speaker_id = st.number_input(
                        "speaker_id", min_value=0,
                        value=int(prev.get("speaker_id", 3)), step=1,
                        key=f"sid_{speaker}",
                    )
            with c2:
                speed = st.slider(
                    "話速", 0.5, 2.0, value=float(prev.get("speed_scale", 1.0)),
                    step=0.05, key=f"speed_{speaker}",
                )
            with c3:
                pitch = st.slider(
                    "ピッチ", -0.15, 0.15, value=float(prev.get("pitch_scale", 0.0)),
                    step=0.01, key=f"pitch_{speaker}",
                )

        speaker_map[speaker] = {
            "speaker_id": speaker_id,
            "speed_scale": speed,
            "pitch_scale": pitch,
        }

    with st.expander("プレビュー（最初の3発言）"):
        preview = [e for e in entries if e["type"] == "line"][:3]
        for e in preview:
            cfg = speaker_map.get(e["speaker"], {})
            sid = cfg.get("speaker_id", "?")
            char_label = next((c["label"] for c in chars if c["id"] == sid), f"ID:{sid}")
            spd = cfg.get("speed_scale", 1.0)
            st.markdown(
                f"**{e['speaker']}** → {char_label} / 話速 {spd}  \n"
                f"> {e['text'][:80]}{'…' if len(e['text']) > 80 else ''}"
            )

    col_back, col_next = st.columns([1, 1])
    with col_back:
        if st.button("← 戻る", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with col_next:
        if st.button("次へ: 音声生成 →", type="primary", use_container_width=True):
            st.session_state.speaker_map = speaker_map
            st.session_state.step = 3
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — 音声生成・ダウンロード
# ══════════════════════════════════════════════════════════════════════════════

elif step == 3:
    st.subheader("音声を生成する")

    with st.expander("詳細設定"):
        st.session_state.silence_lines = st.slider(
            "発言間の無音（秒）", 0.0, 3.0,
            value=float(st.session_state.silence_lines), step=0.1,
        )
        st.session_state.silence_sections = st.slider(
            "セクション区切りの無音（秒）", 0.5, 5.0,
            value=float(st.session_state.silence_sections), step=0.1,
        )

    if st.session_state.output_bytes:
        st.success("✅ 変換完了！")
        col_dl, col_re = st.columns([2, 1])
        with col_dl:
            st.download_button(
                label="⬇️ MP3をダウンロード",
                data=st.session_state.output_bytes,
                file_name=st.session_state.output_filename,
                mime="audio/mpeg",
                type="primary",
                use_container_width=True,
            )
        with col_re:
            if st.button("別のテキストを変換", use_container_width=True):
                _reset()
                st.rerun()
        st.divider()

    col_back, col_gen = st.columns([1, 2])
    with col_back:
        if st.button("← 話者設定に戻る", use_container_width=True):
            st.session_state.step = 2
            st.session_state.output_bytes = None
            st.rerun()
    with col_gen:
        btn_label = "🎙 もう一度生成する" if st.session_state.output_bytes else "🎙 音声を生成する"
        if st.button(btn_label, type="primary", use_container_width=True):
            st.session_state.output_bytes = None
            _run_synthesis(
                entries=st.session_state.parsed_entries,
                speaker_map=st.session_state.speaker_map,
                silence_lines=st.session_state.silence_lines,
                silence_sections=st.session_state.silence_sections,
            )

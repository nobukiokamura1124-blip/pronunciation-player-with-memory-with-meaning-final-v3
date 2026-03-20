import streamlit as st
from gtts import gTTS
import tempfile
from supabase import create_client
import requests
from openai import OpenAI

# =============================
# アプリ基本設定
# =============================
st.set_page_config(page_title="Pronunciation Player")
st.title("🎧 Pronunciation + Meaning")

# =============================
# Supabase接続
# =============================
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# =============================
# OpenAIクライアント
# =============================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =============================
# GPTで意味取得（そのまま）
# =============================
def get_meaning(word):
    try:
        prompt = f"""
        英単語: {word}

        以下を簡潔に出力してください：
        ・日本語の意味（自然な表現、カタカナ禁止）
        ・英語の簡単な定義（短く）
        ・例文（簡単な英語）

        フォーマット：
        🇯🇵 日本語
        🇬🇧 英語
        💡 例文
        """

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        return res.choices[0].message.content.strip()

    except:
        return "意味取得エラー"

# =============================
# ⭐ 追加：キャッシュ
# =============================
@st.cache_data
def get_meaning_cached(word):
    return get_meaning(word)

# =============================
# データ操作（CRUD）
# =============================
def load_data():
    res = supabase.table("word_lists").select("name, words").execute()
    return {row["name"]: row["words"] for row in res.data}

def save_new(name, words):
    supabase.table("word_lists").insert({
        "name": name,
        "words": words
    }).execute()

def update_existing(name, words):
    supabase.table("word_lists").update({
        "words": words
    }).eq("name", name).execute()

def delete_list(name):
    supabase.table("word_lists").delete().eq("name", name).execute()

# =============================
# セッション管理
# =============================
if "loaded_words" not in st.session_state:
    st.session_state.loaded_words = []

if "input_count" not in st.session_state:
    st.session_state.input_count = 10

if "input_version" not in st.session_state:
    st.session_state.input_version = 0

if "audio_cache" not in st.session_state:
    st.session_state.audio_cache = {}

if "current_list" not in st.session_state:
    st.session_state.current_list = ""

if "show_new_name_input" not in st.session_state:
    st.session_state.show_new_name_input = False

# =============================
# リセット
# =============================
if st.button("🧹 クリア"):
    st.session_state.loaded_words = []
    st.session_state.input_count = 10
    st.session_state.input_version += 1
    st.session_state.current_list = ""
    st.session_state.show_new_name_input = False
    st.rerun()

# =============================
# 単語入力
# =============================
st.write("### 単語入力")

words = []

while len(st.session_state.loaded_words) < st.session_state.input_count:
    st.session_state.loaded_words.append("")

for i in range(st.session_state.input_count):
    val = st.text_input(
        f"{i+1}",
        value=st.session_state.loaded_words[i],
        key=f"text_{i}_{st.session_state.input_version}"
    )
    st.session_state.loaded_words[i] = val
    if val.strip():
        words.append(val.strip())

if st.button("＋ 単語追加"):
    st.session_state.input_count += 5
    st.rerun()

# =============================
# 音声生成
# =============================
def get_audio(text):
    if text in st.session_state.audio_cache:
        return st.session_state.audio_cache[text]

    tts = gTTS(text=text, lang="en")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    tts.save(tmp.name)

    st.session_state.audio_cache[text] = tmp.name
    return tmp.name

# =============================
# 発音＋意味
# =============================
if words:
    st.write("### 発音 ＋ 意味")

    for i, w in enumerate(words):
        col1, col2 = st.columns([2, 3])

        with col1:
            if st.button(w, key=f"play_{i}_{w}"):
                st.audio(get_audio(w))

        with col2:
            st.write(get_meaning_cached(w))  # ←ここだけ変更

# =============================
# DB操作
# =============================
st.write("### 単語リスト")

data = load_data()

mode = "新規モード" if not st.session_state.current_list else f"編集中：{st.session_state.current_list}"
st.write(f"状態：{mode}")

# 新規保存
if not st.session_state.current_list:
    new_name = st.text_input("新しいリスト名")

    if st.button("保存"):
        if new_name and words:
            if new_name in data:
                st.warning("既に存在します")
            else:
                save_new(new_name, words)
                st.success("保存しました")
                st.rerun()

# 編集モード
else:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("上書き"):
            update_existing(st.session_state.current_list, words)
            st.success("更新しました")
            st.rerun()

    with col2:
        if st.button("別名保存"):
            st.session_state.show_new_name_input = True

    if st.session_state.show_new_name_input:
        new_name = st.text_input("新しい名前")

        if st.button("実行"):
            if new_name and words:
                if new_name in data:
                    st.warning("既に存在します")
                else:
                    save_new(new_name, words)
                    st.success("保存しました")
                    st.session_state.show_new_name_input = False
                    st.rerun()

# =============================
# リスト操作
# =============================
if data:
    selected = st.selectbox("リスト選択", list(data.keys()))

    if st.button("読み込み"):
        st.session_state.loaded_words = data[selected].copy()
        st.session_state.input_count = max(10, len(data[selected]))
        st.session_state.input_version += 1
        st.session_state.current_list = selected
        st.session_state.show_new_name_input = False
        st.rerun()

    if st.button("削除"):
        delete_list(selected)
        st.success("削除しました")
        st.session_state.current_list = ""
        st.rerun()

# =============================
# スタイル
# =============================
st.markdown("""
<style>
button {
    font-size: 18px !important;
    padding: 8px !important;
}
</style>
""", unsafe_allow_html=True)
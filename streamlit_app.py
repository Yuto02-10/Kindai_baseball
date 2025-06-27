import streamlit as st
import pandas as pd
import math
import random
import plotly.graph_objects as go
import glob
import os
import base64

# 1. 再現性のためランダムシードを固定
random.seed(42)

# --- 定数定義 ---
# 設定値を関数の外に出し、可読性とメンテナンス性を向上
RANK_TO_DISTANCE = {
    1: 10, 2: 65, 3: 110, 4: 155, 5: 195,
    6: 240, 7: 290,
}
DIRECTION_TO_ANGLE = {
    'B': -46.5, 'C': -42.2, 'D': -38, 'E': -34.2,
    'F': -30, 'G': -26, 'H': -22.15,'I': -18, 'J': -14,
    'K': -10, 'L': -6, 'M': -2.5, 'N': 1.5, 'O': 5.5,
    'P': 9.5, 'Q': 13.5, 'R': 17.5, 'S': 21.5, 'T': 25.5,
    'U': 29.5, 'V': 33.5, 'W': 37.5, 'X': 41.5, 'Y': 45.5,
}
COLOR_MAP = {"ゴロ": "green", "フライ": "blue", "ライナー": "red", "バント": "orange"}
SYMBOL_MAP = {
    "ストレート": "circle", "カーブ": "diamond", "スライダー": "square",
    "チェンジ": "triangle-up", "フォーク": "x", "不明": "cross", "カット": "triangle-right",
    "シュート": "triangle-left",
}

# 2. 背景画像をbase64エンコード
@st.cache_data
def load_background_image(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    encoded_image = base64.b64encode(image_bytes).decode()
    return f"data:image/png;base64,{encoded_image}"

# 3. MemoをXY座標に変換
def parse_memo_to_xy_random_fixed(memo, angle_range=0.05, distance_range=0.1):
    if isinstance(memo, str) and len(memo) >= 2:
        direction = memo[0].upper()
        try:
            distance_rank = int(memo[1])
        except (ValueError, IndexError):
            return pd.Series([None, None])

        angle_center = DIRECTION_TO_ANGLE.get(direction)
        base_distance = RANK_TO_DISTANCE.get(distance_rank)

        if angle_center is None or base_distance is None:
            return pd.Series([None, None])

        angle_deg = angle_center + random.uniform(-angle_range, angle_range)
        distance = base_distance * random.uniform(1 - distance_range, 1 + distance_range)
        angle_rad = math.radians(angle_deg)
        
        a_scale = 1.2
        b_scale = 0.8
        x = round(distance * a_scale * math.sin(angle_rad), 2)
        y = round(distance * b_scale * math.cos(angle_rad), 2)
        return pd.Series([x, y])
    else:
        return pd.Series([None, None])

# 4. 色・マーカー設定関数
def get_color_by_hittype(hittype):
    return COLOR_MAP.get(hittype, "gray")

def get_symbol_by_pitchtype(pitchtype):
    return SYMBOL_MAP.get(pitchtype, "circle")

# 5. データ読み込みと前処理
@st.cache_data
def load_and_preprocess_data(folder_path):
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not csv_files:
        return pd.DataFrame()

    df_list = []
    for file in csv_files:
        try:
            df = pd.read_csv(file, encoding='utf-8') # or 'cp932'
            df["試合"] = os.path.basename(file)
            df_list.append(df)
        except Exception as e:
            st.warning(f"ファイル {file} の読み込み中にエラーが発生しました: {e}")
            
    if not df_list:
        return pd.DataFrame()

    df_all = pd.concat(df_list, ignore_index=True)
    df_all[['打球X', '打球Y']] = df_all['Memo'].apply(parse_memo_to_xy_random_fixed)
    
    # 解析に必要なカラムが存在するか確認
    required_cols = ['Batter', 'PitchType', 'HitType', 'Memo']
    if not all(col in df_all.columns for col in required_cols):
        st.error(f"読み込んだCSVには、必須カラム（{', '.join(required_cols)}）が含まれていません。")
        return pd.DataFrame()
        
    df_all = df_all.dropna(subset=['打球X', '打球Y'])
    return df_all

# 6. Streamlit アプリ本体
def main():
    st.set_page_config(layout="wide")
    st.title("打球方向可視化アプリ")

    # --- パス設定 ---
    image_path = "打球分析.png"
    folder_path = "試合データ"

    if not os.path.exists(image_path) or not os.path.exists(folder_path):
        st.error("背景画像 `打球分析.png` または `試合データ` フォルダが見つかりません。")
        return

    # --- データ読み込み ---
    df_all = load_and_preprocess_data(folder_path)
    if df_all.empty:
        st.error("表示できるデータがありません。`試合データ` フォルダにCSVファイルを確認してください。")
        return

    image_source = load_background_image(image_path)
    
    # --- サイドバー (フィルター) ---
    st.sidebar.header("フィルター設定")

    # 打者選択
    batters = ["全選手"] + sorted(df_all['Batter'].dropna().unique())
    selected_batter = st.sidebar.selectbox("打者を選択", options=batters)

    # 試合選択
    games = ["全試合"] + sorted(df_all['試合'].dropna().unique())
    selected_game = st.sidebar.selectbox("試合を選択", options=games)

    # 打球種類フィルター
    hit_types = sorted(df_all['HitType'].dropna().unique())
    selected_hit_types = st.sidebar.multiselect("打球種類", options=hit_types, default=hit_types)
    
    # 球種フィルター
    pitch_filter = st.sidebar.radio("球種フィルター", options=["すべて", "ストレート", "変化球"])
    
    # ★★★ 新機能: カウントフィルター ★★★
    selected_ball, selected_strike = None, None
    if 'Ball' in df_all.columns and 'Strike' in df_all.columns:
        st.sidebar.subheader("カウントフィルター")
        ball_options = ["すべて"] + sorted(df_all['Ball'].dropna().unique().astype(int))
        selected_ball = st.sidebar.selectbox("ボールカウント", options=ball_options)

        strike_options = ["すべて"] + sorted(df_all['Strike'].dropna().unique().astype(int))
        selected_strike = st.sidebar.selectbox("ストライクカウント", options=strike_options)
    else:
        st.sidebar.warning("CSVに 'Ball'/'Strike' カラムがないため、カウントフィルターは無効です。")

    # --- データフィルタリング ---
    df_filtered = df_all.copy()
    if selected_batter != "全選手":
        df_filtered = df_filtered[df_filtered['Batter'] == selected_batter]
    if selected_game != "全試合":
        df_filtered = df_filtered[df_filtered['試合'] == selected_game]
    if selected_hit_types:
        df_filtered = df_filtered[df_filtered['HitType'].isin(selected_hit_types)]
    
    if pitch_filter == "ストレート":
        df_filtered = df_filtered[df_filtered['PitchType'] == "ストレート"]
    elif pitch_filter == "変化球":
        df_filtered = df_filtered[~df_filtered['PitchType'].isin(["ストレート", "不明"])]
    
    # ★★★ 新機能: カウントによる絞り込み ★★★
    if selected_ball is not None and selected_ball != "すべて":
        df_filtered = df_filtered[df_filtered['Ball'] == selected_ball]
    if selected_strike is not None and selected_strike != "すべて":
        df_filtered = df_filtered[df_filtered['Strike'] == selected_strike]

    # --- メインコンテンツ ---
    col1, col2 = st.columns([3, 1])

    with col1:
        # ★★★ グラフタイトルを更新 ★★★
        title_text = f"打者: {selected_batter}"
        if selected_game != "全試合":
            title_text += f" | 試合: {selected_game}"
        
        count_text_parts = []
        if selected_ball is not None and selected_ball != 'すべて':
            count_text_parts.append(f"B:{selected_ball}")
        if selected_strike is not None and selected_strike != 'すべて':
            count_text_parts.append(f"S:{selected_strike}")
        if count_text_parts:
            title_text += f" | カウント: {'-'.join(count_text_parts)}"

        title_text += f" ({len(df_filtered)}球)"
        st.subheader(title_text)

        # --- グラフ作成 ---
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_filtered['打球X'],
            y=df_filtered['打球Y'],
            mode="markers",
            marker=dict(
                size=10,
                color=[get_color_by_hittype(ht) for ht in df_filtered['HitType']],
                symbol=[get_symbol_by_pitchtype(pt) for pt in df_filtered['PitchType']],
                line=dict(width=1, color='DarkSlateGrey')
            ),
            text=[f"選手: {b}<br>打球: {h}<br>球種: {p}<br>カウント: {int(ba)}-{int(s)}<br>メモ: {m}" 
                  for b, h, p, m, ba, s in zip(df_filtered['Batter'], df_filtered['HitType'], df_filtered['PitchType'], df_filtered['Memo'], df_filtered['Ball'], df_filtered['Strike'])],
            hoverinfo='text',
            name=selected_batter,
        ))

        fig.update_layout(
            xaxis=dict(range=[-200, 200], showgrid=False, zeroline=False, showticklabels=False, title=None),
            yaxis=dict(range=[-20, 240], showgrid=False, zeroline=False, showticklabels=False, title=None),
            width=800, height=700,
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=40, b=20),
            images=[dict(
                source=image_source,
                xref="x", yref="y",
                x=-292.5, y=296.25,
                sizex=585, sizey=315,
                sizing="stretch",
                opacity=1,
                layer="below"
            )]
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("データサマリー")
        if not df_filtered.empty:
            st.write("#### 打球種類")
            hit_summary = df_filtered['HitType'].value_counts().reset_index()
            hit_summary.columns = ['種類', '球数']
            st.dataframe(hit_summary, use_container_width=True)
            
            st.write("#### 打った球種")
            pitch_summary = df_filtered['PitchType'].value_counts().reset_index()
            pitch_summary.columns = ['球種', '球数']
            st.dataframe(pitch_summary, use_container_width=True)
        else:
            st.info("表示するデータがありません。")

if __name__ == "__main__":
    main()

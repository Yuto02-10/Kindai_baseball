import streamlit as st
import pandas as pd
import math
import random
import plotly.graph_objects as go
import glob
import os
from PIL import Image
import base64

# 1. 再現性のためランダムシードを固定
random.seed(42)

# 2. 背景画像をbase64エンコード
def load_background_image(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    encoded_image = base64.b64encode(image_bytes).decode()
    return f"data:image/png;base64,{encoded_image}"

# 3. MemoをXY座標に変換（ランダム微調整＋楕円）
def parse_memo_to_xy_random_fixed(memo, angle_range=0.05, distance_range=0.1):
    rank_to_distance = {
        1: 10, 2: 65, 3: 110, 4: 155, 5: 195,
        6: 240, 7: 290,
    }
    direction_to_angle = {
         'B': -46.5, 'C': -42.2, 'D': -38, 'E': -34.2,
        'F': -30, 'G': -26, 'H': -22.15,'I': -18, 'J': -14,
        'K': -10, 'L': -6, 'M': -2.5, 'N': 1.5, 'O': 5.5,
        'P': 9.5, 'Q': 13.5, 'R': 17.5, 'S': 21.5, 'T': 25.5,
        'U': 29.5, 'V': 33.5, 'W': 37.5, 'X': 41.5, 'Y': 45.5,
    }
    if isinstance(memo, str) and len(memo) >= 2:
        direction = memo[0].upper()
        try:
            distance_rank = int(memo[1])
        except ValueError:
            return pd.Series([None, None])
        angle_center = direction_to_angle.get(direction, None)
        if angle_center is None or distance_rank not in rank_to_distance:
            return pd.Series([None, None])
        angle_deg = angle_center + random.uniform(-angle_range, angle_range)
        base_distance = rank_to_distance[distance_rank]
        distance = base_distance * random.uniform(1 - distance_range, 1 + distance_range)
        angle_rad = math.radians(angle_deg)
        a_scale = 1.2
        b_scale = 0.8
        x = round(distance * a_scale * math.sin(angle_rad), 2)
        y = round(distance * b_scale * math.cos(angle_rad), 2)
        return pd.Series([x, y])
    else:
        return pd.Series([None, None])

# 4. 色・マーカー設定
def get_color_by_hittype(hittype):
    color_map = {"ゴロ": "green", "フライ": "blue", "ライナー": "red", "バント": "orange"}
    return color_map.get(hittype, "gray")

def get_symbol_by_pitchtype(pitchtype):
    symbol_map = {
        "ストレート": "circle", "カーブ": "diamond", "スライダー": "square",
        "チェンジ": "triangle-up", "フォーク": "x", "不明": "cross", "カット": "triangle-right",
        "シュート": "triangle-left",
    }
    return symbol_map.get(pitchtype, "circle")

# 5. Streamlit アプリ
def main():
    st.title("打球方向可視化アプリ")

    # データと背景画像のパス指定
    image_path = "打球分析.png"  # プロジェクトフォルダ直下に置いてください
    folder_path = "試合データ"     # 同じくプロジェクトフォルダ直下に "試合データ" フォルダ

    if not os.path.exists(image_path) or not os.path.exists(folder_path):
        st.error("背景画像または試合データフォルダが見つかりません。")
        return

    image_source = load_background_image(image_path)

    # CSV一括読み込み
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not csv_files:
        st.error("CSVファイルが見つかりません。")
        return

    df_list = []
    for file in csv_files:
        df = pd.read_csv(file)
        df["ファイル名"] = os.path.basename(file)
        df_list.append(df)

    df = pd.concat(df_list, ignore_index=True)
    df[['打球X', '打球Y']] = df['Memo'].apply(lambda x: parse_memo_to_xy_random_fixed(x))

    batters = df['Batter'].dropna().unique()

    # 打者選択
    selected_batter = st.selectbox("打者を選択", options=batters)

    # 球種フィルター
    pitch_filter = st.selectbox("球種フィルター", options=["すべて", "ストレート", "その他"])

    # データフィルタリング
    df_batter = df[df['Batter'] == selected_batter]
    if pitch_filter == "ストレート":
        df_batter = df_batter[df_batter['PitchType'] == "ストレート"]
    elif pitch_filter == "その他":
        df_batter = df_batter[df_batter['PitchType'] != "ストレート"]

    # グラフ作成
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_batter['打球X'],
        y=df_batter['打球Y'],
        mode="markers",
        marker=dict(
            size=8,
            color=[get_color_by_hittype(ht) for ht in df_batter['HitType']],
            symbol=[get_symbol_by_pitchtype(pt) for pt in df_batter['PitchType']]
        ),
        text=[f"{m} / {h} / {p}" for m, h, p in zip(df_batter['Memo'], df_batter['HitType'], df_batter['PitchType'])],
        textposition="top center",
        name=selected_batter,
    ))

    fig.update_layout(
        xaxis=dict(range=[-200, 200], showgrid=False, zeroline=False, showticklabels=True, title=None),
        yaxis=dict(range=[-20, 240], showgrid=False, zeroline=False, showticklabels=True, title=None),
        width=800, height=700, plot_bgcolor="white",
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

    st.plotly_chart(fig)

if __name__ == "__main__":
    main()

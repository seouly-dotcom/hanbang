import streamlit as st
import pandas as pd
import re
import os

# --- 프로그램 설정 ---
st.set_page_config(page_title="스마트 한의 처방 시스템", layout="wide", page_icon="🌿")

# --- 스타일(CSS) 설정 ---
st.markdown("""
<style>
    .big-font { font-size: 20px !important; font-weight: bold; }
    .stDataFrame { border: 1px solid #ddd; border-radius: 5px; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #0068c9; }
</style>
""", unsafe_allow_html=True)

# --- 1. 데이터 로드 및 전처리 ---
@st.cache_data
def load_data():
    df = pd.DataFrame()
    try:
        df = pd.read_csv('formulas.csv', encoding='utf-8')
    except:
        try:
            df = pd.read_csv('formulas.csv', encoding='cp949')
        except:
            return pd.DataFrame()
            
    if not df.empty:
        if '약어' not in df.columns:
            df['약어'] = ""
        
        def create_display_name(row):
            if pd.notna(row['약어']) and str(row['약어']).strip() != "":
                return f"{row['처방명']} ({row['약어']})"
            else:
                return row['처방명']
        
        if '처방명' in df.columns:
            df['검색용이름'] = df.apply(create_display_name, axis=1)
        else:
            return pd.DataFrame()
    return df

def parse_herb(herb_str):
    numbers = re.findall(r"[\d.]+", str(herb_str))
    names = re.findall(r"[가-힣]+", str(herb_str))
    if names and numbers:
        return names[0], float(numbers[0])
    elif names and not numbers:
        return names[0], 0.0
    else:
        return None, 0.0

# --- 데이터 불러오기 ---
df = load_data()

# 변수 초기화
selected_display = []
multiplier = 1.0
cheop_su = 20

# --- 2. 사이드바 ---
with st.sidebar:
    st.title("🗂️ 처방 선택")
    
    if not df.empty:
        options = df['검색용이름'].tolist()
        selected_display = st.multiselect(
            "처방 검색 (약어 가능)",
            options=options,
            placeholder="예: 갈근탕, 소청..."
        )
        
        st.markdown("---")
        st.subheader("⚙️ 용량 설정")
        
        cheop_su = st.number_input("1. 몇 첩(Cheop) 달이시나요?", min_value=1, value=20, step=1)
        
        st.write("") 
        multiplier = st.number_input(
            "2. 처방 강도 배율 (예: 0.8, 1.2)", 
            min_value=0.1, 
            value=1.0, 
            step=0.1, 
            format="%.1f"
        )
        
        if multiplier == 1.0:
            st.info(f"💡 기본 용량 (1.0배)")
        elif multiplier > 1.0:
            st.warning(f"🔥 **{multiplier}배** 진하게(증량)")
        else:
            st.success(f"📉 **{multiplier}배** 순하게(감량)")
            
        st.markdown("---")
        if st.button("🔄 초기화"):
            st.rerun()
    else:
        st.error("⚠️ 데이터 파일을 찾을 수 없습니다!")

# --- 3. 메인 화면 ---
st.title("🌿 스마트 처방 운용 시스템")

if not df.empty:
    if selected_display:
        selected_rows = df[df['검색용이름'].isin(selected_display)]
        
        # 1. 기본 데이터 계산 (원방 기준 합산)
        herb_dict = {}
        for composition in selected_rows['구성약재']:
            items = str(composition).split(',')
            for item in items:
                name, amount = parse_herb(item)
                if name:
                    if name in herb_dict:
                        herb_dict[name] = max(herb_dict[name], amount)
                    else:
                        herb_dict[name] = amount
        
        # 2. 배율 적용 (계산 단계에서 먼저 곱함)
        if multiplier != 1.0:
            for k, v in herb_dict.items():
                herb_dict[k] = v * multiplier

        unique_key = f"editor_{len(selected_display)}_{multiplier}_{cheop_su}"

        # 3. [핵심] 반올림(round) 후 정수(int) 변환
        initial_data = pd.DataFrame([
            {"약재명": k, "1첩 용량(g)": int(round(v)), "비고": ""} 
            for k, v in herb_dict.items()
        ])
        initial_data = initial_data.sort_values("약재명")

        col_left, col_right = st.columns([1.2, 1])

        with col_left:
            st.subheader("📝 처방 구성 및 가감(加減)")
            if multiplier != 1.0:
                st.warning(f"⚡ 표의 숫자는 **{multiplier}배** 적용 후 **반올림**된 용량입니다.")
            else:
                st.caption(f"현재 기본 용량(1.0배)입니다.")

            # ★ 에러가 났던 부분이 바로 여기입니다 (괄호 확인 완료) ★
            edited_df = st.data_editor(
                initial_data,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "약재명": st.column_config.TextColumn("약재명", required=True),
                    "1첩 용량(g)": st.column_config.NumberColumn("1첩 용량(g)", min_value=0, format="%d"),
                    "비고": st.column_config.TextColumn("비고")
                },
                key=unique_key 
            )
            
            with st.expander("참고: 원본 처방 구성"):
                for idx, row in selected_rows.iterrows():
                    st.write(f"**{row['처방명']}:** {row['구성약재']}")

        with col_right:
            if multiplier != 1.0:
                st.subheader(f"📊 최종 처방전 ({cheop_su}첩 × {multiplier}배)")
            else:
                st.subheader(f"📊 최종 처방전 ({cheop_su}첩)")
            
            if not edited_df.empty:
                # 총량 계산
                edited_df["총 용량(g)"] = edited_df["1첩 용량(g)"] * cheop_su
                
                sorted_result = edited_df.sort_values(by="1첩 용량(g)", ascending=False)
                
                total_weight_1 = edited_df["1첩 용량(g)"].sum()
                total_weight_final = edited_df["총 용량(g)"].sum()
                
                m1, m2 = st.columns(2)
                m1.metric(f"1첩 ({multiplier}배)", f"{int(total_weight_1)} g")
                m2.metric(f"총 무게 ({cheop_su}첩)", f"{int(total_weight_final)} g")
                
                st.divider()
                st.markdown("##### 📋 탕전실 전달용")
                
                final_text_list = []
                for idx, row in sorted_result.iterrows():
                    if row['약재명'] and row['1첩 용량(g)'] > 0:
                        final_text_list.append(f"{row['약재명']} {int(row['총 용량(g)'])}g")
                
                result_text = ", ".join(final_text_list)
                st.text_area("복사해서 차트에 붙여넣으세요", result_text, height=200)
                
                st.dataframe(sorted_result[['약재명', '1첩 용량(g)', '총 용량(g)']], hide_index=True, use_container_width=True)
                st.success("작성이 완료되었습니다.")

    else:
        st.info("👈 왼쪽 사이드바에서 처방을 검색하여 시작하세요.")
else:
    st.error("⚠️ 데이터 파일을 찾을 수 없습니다!")
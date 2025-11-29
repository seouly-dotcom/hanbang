import streamlit as st
import pandas as pd
import re

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
    try:
        df = pd.read_csv('formulas.csv', encoding='utf-8')
    except:
        try:
            df = pd.read_csv('formulas.csv', encoding='cp949')
        except:
            return pd.DataFrame()
    
    if '약어' not in df.columns:
        df['약어'] = ""
    
    def create_display_name(row):
        if pd.notna(row['약어']) and str(row['약어']).strip() != "":
            return f"{row['처방명']} ({row['약어']})"
        else:
            return row['처방명']
            
    df['검색용이름'] = df.apply(create_display_name, axis=1)
    return df

# 약재 파싱 함수
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

# --- 2. 사이드바 (처방 선택 및 설정) ---
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
        
        # 1. 첩수 설정
        cheop_su = st.number_input("1. 몇 첩(Cheop) 달이시나요?", min_value=1, value=20, step=1)
        
        # 2. 배율 설정 (0.1단위로 자유롭게 조절 가능)
        st.write("") 
        multiplier = st.number_input(
            "2. 처방 강도 배율 (예: 0.8, 1.2)", 
            min_value=0.1, 
            value=1.0, 
            step=0.1, 
            format="%.1f"
        )
        
        # 배율에 따른 안내 메시지 (자동 변경)
        if multiplier == 1.0:
            st.info(f"💡 기본 용량 (1.0배) 정량 처방")
        elif multiplier > 1.0:
            st.warning(f"🔥 **{multiplier}배** 진하게(증량) 처방합니다!")
        else:
            st.success(f"📉 **{multiplier}배** 순하게(감량) 처방합니다. (소아/노인)")
            
        st.markdown("---")
        if st.button("🔄 초기화"):
            st.rerun()

# --- 3. 메인 화면 ---
st.title("🌿 스마트 처방 운용 시스템")

if selected_display:
    selected_rows = df[df['검색용이름'].isin(selected_display)]
    
    # 약재 합산 로직 (Max Value 기준)
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
    
    # 편집용 데이터 생성
    initial_data = pd.DataFrame([
        {"약재명": k, "1첩 용량(g)": v, "비고": ""} 
        for k, v in herb_dict.items()
    ])
    initial_data = initial_data.sort_values("약재명")

    col_left, col_right = st.columns([1.2, 1])

    # [왼쪽] 처방 편집기
    with col_left:
        st.subheader("📝 처방 구성 및 가감(加減)")
        st.caption(f"현재 **{multiplier}배** 농도로 계산 중입니다. 표의 수치는 **1첩 원방 기준**입니다.")

        edited_df = st.data_editor(
            initial_data,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "약재명": st.column_config.TextColumn("약재명", required=True),
                "1첩 용량(g)": st.column_config.NumberColumn("1첩 용량(g)", min_value=0.0, format="%.1f"),
                "비고": st.column_config.TextColumn("비고")
            },
            key="editor"
        )
        
        with st.expander("참고: 원본 처방 구성"):
            for idx, row in selected_rows.iterrows():
                st.write(f"**{row['처방명']}:** {row['구성약재']}")

    # [오른쪽] 최종 계산서 (배율 적용됨)
    with col_right:
        # 제목에 배율 표시
        if multiplier != 1.0:
            st.subheader(f"📊 최종 처방전 ({cheop_su}첩 × {multiplier}배)")
        else:
            st.subheader(f"📊 최종 처방전 ({cheop_su}첩)")
        
        if not edited_df.empty:
            # ★ 총량 계산 공식: 1첩용량 * 첩수 * 배율 ★
            edited_df["총 용량(g)"] = edited_df["1첩 용량(g)"] * cheop_su * multiplier
            
            # 정렬: 용량이 큰 순서대로
            sorted_result = edited_df.sort_values(by="1첩 용량(g)", ascending=False)
            
            # 합계 보여주기
            total_weight_1 = edited_df["1첩 용량(g)"].sum()
            total_weight_final = edited_df["총 용량(g)"].sum()
            
            m1, m2 = st.columns(2)
            m1.metric("1첩 기준량", f"{total_weight_1:.1f} g")
            # 배율이 적용된 최종 무게
            m2.metric(f"총 무게 ({multiplier}배)", f"{total_weight_final:.1f} g")
            
            st.divider()
            
            st.markdown("##### 📋 탕전실 전달용 (용량순)")
            
            final_text_list = []
            for idx, row in sorted_result.iterrows():
                if row['약재명'] and row['1첩 용량(g)'] > 0:
                    # 텍스트에는 총량만 깔끔하게 표시
                    final_text_list.append(f"{row['약재명']} {row['총 용량(g)']:.1f}g")
            
            result_text = ", ".join(final_text_list)
            st.text_area("복사해서 차트에 붙여넣으세요", result_text, height=200)
            
            # 상세 표
            st.dataframe(
                sorted_result[['약재명', '1첩 용량(g)', '총 용량(g)']], 
                hide_index=True,
                use_container_width=True
            )
            
            st.success("작성이 완료되었습니다.")

else:
    st.info("👈 왼쪽 사이드바에서 처방을 검색하여 시작하세요.")
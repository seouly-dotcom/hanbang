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

# --- 🔍 [CCTV] 파일 목록 확인 기능 ---
st.title("🌿 스마트 처방 운용 시스템")

# 현재 폴더에 있는 모든 파일을 가져옵니다
current_files = os.listdir('.')

# formulas.csv와 비슷한 파일이 있는지 찾습니다
target_file = 'formulas.csv'
found_file = None

# 대소문자 무시하고 찾기
for f in current_files:
    if f.lower() == target_file.lower():
        found_file = f
        break

# --- 진단 결과 표시 ---
if found_file:
    if found_file != target_file:
        st.warning(f"⚠️ 파일 이름이 조금 다릅니다! (현재: {found_file} / 정답: {target_file})")
        st.info("그래도 찾았으니 일단 실행합니다.")
    # 실제 찾은 파일 이름으로 로드 시도
    real_filename = found_file
else:
    st.error("❌ 'formulas.csv' 파일을 못 찾았습니다.")
    st.write("👇 **서버가 보고 있는 파일 목록 (여기에 formulas.csv가 있나요?)**")
    st.code(current_files)
    st.stop() # 프로그램 중단

# --- 1. 데이터 로드 및 전처리 ---
@st.cache_data
def load_data(filename):
    df = pd.DataFrame()
    try:
        df = pd.read_csv(filename, encoding='utf-8')
    except:
        try:
            df = pd.read_csv(filename, encoding='cp949')
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
df = load_data(real_filename)

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
        st.error("⚠️ 파일은 찾았는데 내용이 비어있거나 깨졌습니다!")

# --- 3. 메인 화면 ---
if not df.empty and selected_display:
    selected_rows = df[df['검색용이름'].isin(selected_display)]
    
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
    
    initial_data = pd.DataFrame([
        {"약재명": k, "1첩 용량(g)": v, "비고": ""} 
        for k, v in herb_dict.items()
    ])
    initial_data = initial_data.sort_values("약재명")

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.subheader("📝 처방 구성 및 가감(加減)")
        st.caption(f"현재 **{multiplier}배** 농도입니다.")

        key_val = f"editor_{len(selected_display)}_{multiplier}"
        
        edited_df = st.data_editor(
            initial_data,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "약재명": st.column_config.TextColumn("약재명", required=True),
                "1첩 용량(g)": st.column_config.NumberColumn("1첩 용량(g)", min_value=0.0, format="%.1f"),
                "비고": st.column_config.TextColumn("비고")
            },
            key=key_val
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
            edited_df["총 용량(g)"] = edited_df["1첩 용량(g)"] * cheop_su * multiplier
            sorted_result = edited_df.sort_values(by="1첩 용량(g)", ascending=False)
            
            total_weight_1 = edited_df["1첩 용량(g)"].sum()
            total_weight_final = edited_df["총 용량(g)"].sum()
            
            m1, m2 = st.columns(2)
            m1.metric("1첩 기준량", f"{total_weight_1:.1f} g")
            m2.metric(f"총 무게 ({multiplier}배)", f"{total_weight_final:.1f} g")
            
            st.divider()
            st.markdown("##### 📋 탕전실 전달용")
            
            final_text_list = []
            for idx, row in sorted_result.iterrows():
                if row['약재명'] and row['1첩 용량(g)'] > 0:
                    final_text_list.append(f"{row['약재명']} {row['총 용량(g)']:.1f}g")
            
            result_text = ", ".join(final_text_list)
            st.text_area("복사해서 차트에 붙여넣으세요", result_text, height=200)
            
            st.dataframe(sorted_result[['약재명', '1첩 용량(g)', '총 용량(g)']], hide_index=True, use_container_width=True)
            st.success("작성이 완료되었습니다.")

elif not df.empty and not selected_display:
    st.info("👈 왼쪽 사이드바에서 처방을 검색하여 시작하세요.")
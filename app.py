import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. 페이지 레이아웃 세팅
st.set_page_config(page_title="통합 치료비 조회 시스템", layout="wide")
st.title("🏥 통합 치료비 맞춤형 조회 시스템")
st.caption("사용자별로 선택한 담보와 한도 금액에 맞는 보장 내용을 실시간으로 조회합니다.")

# 2. 구글 시트 연동 및 데이터 캐싱
@st.cache_data(ttl=300)
def load_insurance_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # 원본 구글 스프레드시트 URL
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1S1UsCpUpuBOyn6zb4YDBE_31OJHxCAhsZVVUu-F8dmQ/edit"
    doc = client.open_by_url(spreadsheet_url)
    
    # 실제 구글 시트의 RAW 데이터 가져오기
    # 데이터 구조가 복잡하므로 header가 없는 상태로 가져와서 코드로 가공합니다.
    tabs = {
        "암통치 / 비통치": pd.DataFrame(doc.worksheet("암통치 비통치 - RAW").get_all_values()),
        "순환계 치료비 (순통치)": pd.DataFrame(doc.worksheet("순통치 - RAW").get_all_values()),
        "상해 치료비 (상통치)": pd.DataFrame(doc.worksheet("상통치 - RAW").get_all_values())
    }
    return tabs

try:
    data_dict = load_insurance_data()
except Exception as e:
    st.error("구글 시트 연동 오류! Streamlit Cloud의 Secrets 설정을 확인해주세요.")
    st.stop()

# 3. 사이드바 - 사용자 개별 조건 선택 UI
st.sidebar.header("🔍 보장 조건 선택")

# 🟢 STEP 1: 큰 분류 선택 (암통치, 순통치, 상통치)
category = st.sidebar.selectbox("📋 담보 분류 선택", list(data_dict.keys()))
raw_df = data_dict[category]

st.sidebar.markdown("---")
st.sidebar.subheader("💰 플랜 및 가입한도 설정")

if category == "암통치 / 비통치":
    # 1행에서 상품명 추출 (암통치 기본형, 실속형, 비통치 기본형 등)
    row0 = raw_df.iloc[0].tolist()
    plans = []
    current_plan = ""
    for item in row0:
        if item.strip():
            current_plan = item.strip()
        plans.append(current_plan)
        
    unique_plans = sorted(list(set([p for p in plans if p and "통합치료" not in p])))
    selected_plan = st.sidebar.selectbox("💎 플랜 선택", unique_plans)
    
    # 2행에서 연간 한도 금액 추출 (연 1억, 연 8천 등)
    row1 = raw_df.iloc[1].tolist()
    
    # 선택한 플랜에 해당하는 열 인덱스 찾기
    target_indices = [i for i, p in enumerate(plans) if p == selected_plan]
    available_limits = [row1[i].strip() for i in target_indices if row1[i].strip() and row1[i].strip() != "미선택"]
    
    selected_limit = st.sidebar.selectbox("💵 연간 한도 선택", available_limits)
    
    # 최종 매칭되는 열 인덱스 선택
    final_col_idx = -1
    for i in target_indices:
        if row1[i].strip() == selected_limit:
            final_col_idx = i
            break
            
    # 결과 테이블 조립 (앞의 기준 정보 컬럼 3개 + 선택한 금액 열)
    result_df = raw_df.iloc[2:, [0, 1, 2, final_col_idx]].copy()
    result_df.columns = ["대분류", "중분류", "세부항목", f"{selected_plan} ({selected_limit})"]
    
    # 빈 값 또는 미선택 제거
    result_df = result_df[result_df.iloc[:, 3].str.strip() != "-"]
    result_df = result_df[result_df.iloc[:, 3].str.strip() != ""]

else:
    # 순통치, 상통치는 구조가 상대적으로 단순함 (헤더가 1줄 구조)
    # 1행을 컬럼명으로 지정
    header_row = raw_df.iloc[0].tolist()
    processed_df = raw_df.iloc[1:].copy()
    processed_df.columns = header_row
    
    # '연 1억', '연 8천' 등 금액 관련 컬럼들 필터링
    limit_columns = [col for col in processed_df.columns if any(k in col for k in ["연 ", "천", "억", "기본형"])]
    selected_limit = st.sidebar.selectbox("💵 가입 금액/한도 선택", limit_columns)
    
    base_cols = [col for col in processed_df.columns if col not in limit_columns and col != ""]
    result_df = processed_df[base_cols + [selected_limit]].copy()
    
    # 빈 값 제외
    result_df = result_df[result_df[selected_limit].str.strip() != "-"]
    result_df = result_df[result_df[selected_limit].str.strip() != ""]

# 4. 메인 화면 결과 출력
st.subheader(f"📊 조회 결과")
if category == "암통치 / 비통치":
    st.markdown(f"**선택된 설계:** `{selected_plan}` ➡️ `{selected_limit}`")
else:
    st.markdown(f"**선택된 한도:** `{selected_limit}`")

st.markdown("---")
st.dataframe(result_df, use_container_width=True, hide_index=True)

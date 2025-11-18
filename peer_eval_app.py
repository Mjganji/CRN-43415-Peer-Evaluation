import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION ---
ADMIN_PASSWORD = "TeacherPassword123"  # <--- CHANGE THIS
STUDENT_FILE = "students.csv"
GOOGLE_SHEET_NAME = "Peer Evaluation Results" # Must match your Sheet name exactly

# --- TEXT & CRITERIA ---
TITLE = "Self and Peer Evaluation Feedback Form - MECE 2310U"
CONFIDENTIALITY_TEXT = """
**CONFIDENTIALITY:** This evaluation is a secret vote. Don’t show your vote to others...
**THESE EVALUATIONS WILL NOT BE PUBLISHED; YOUR IDENTITY WILL BE KEPT STRICTLY CONFIDENTIAL.**
"""

CRITERIA = [
    "Attendance at Meetings",
    "Meeting Deadlines",
    "Quality of Work",
    "Amount of Work",
    "Attitudes & Commitment"
]

# --- GOOGLE SHEETS SETUP ---
# This function connects to Google Sheets using the secret key you saved
def get_google_sheet():
    try:
        # Define the scope (what we are allowed to do)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Load credentials from Streamlit Secrets
        s_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(
            s_info, scopes=scopes
        )
        
        # Authorize and open the sheet
        gc = gspread.authorize(credentials)
        return gc.open(GOOGLE_SHEET_NAME).sheet1
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# --- DATA FUNCTIONS ---
@st.cache_data
def load_students():
    try:
        # We still read the student list from the CSV in GitHub because it is static
        df = pd.read_csv(STUDENT_FILE)
        df['Student ID'] = df['Student ID'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error loading student list: {e}")
        return None

def save_to_google_sheets(current_user_id, new_rows):
    sheet = get_google_sheet()
    if not sheet:
        return False
        
    # 1. Get all existing data
    try:
        all_data = sheet.get_all_records()
        df = pd.DataFrame(all_data)
    except:
        df = pd.DataFrame() # Sheet is empty

    # 2. Filter out OLD entries from this user (Overwrite logic)
    if not df.empty and 'Evaluator ID' in df.columns:
        # We keep rows where Evaluator ID is NOT the current user
        # Note: Sheets returns ints or strings, so we convert to string to be safe
        df['Evaluator ID'] = df['Evaluator ID'].astype(str)
        df = df[df['Evaluator ID'] != str(current_user_id)]
    
    # 3. Add the NEW data
    new_df = pd.DataFrame(new_rows)
    
    # Combine old (others) + new (current user)
    final_df = pd.concat([df, new_df], ignore_index=True)
    
    # 4. Clear Sheet and Rewrite (This is the safest way to ensure overwrite)
    # We convert DataFrame to list of lists for gspread
    sheet.clear()
    # Add headers
    sheet.append_row(final_df.columns.tolist())
    # Add data
    sheet.append_rows(final_df.values.tolist())
    return True

# --- MAIN APP ---
st.set_page_config(page_title="Peer Evaluation", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("Teacher Access")
    if st.text_input("Password", type="password") == ADMIN_PASSWORD:
        st.success("Connected to Google Sheets")
        st.info("Check your Google Sheet named 'Peer Evaluation Results' to see live data.")
        
        if st.button("Calculate Grades Now"):
            sheet = get_google_sheet()
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if not df.empty:
                summary = df.groupby('Peer Name')['Overall Score'].mean().reset_index()
                st.dataframe(summary)
            else:
                st.warning("No data yet.")

# --- LOGIN PAGE ---
if st.session_state['user'] is None:
    st.title(TITLE)
    st.subheader("Step 1: Identification")
    df_students = load_students()
    if df_students is not None:
        names = sorted(df_students['Student Name'].unique().tolist())
        selected_name = st.selectbox("Select your name:", [""] + names)
        student_id = st.text_input("Enter your Student Number (Password):", type="password")
        
        if st.button("Login"):
            user_record = df_students[(df_students['Student Name'] == selected_name) & (df_students['Student ID'] == student_id)]
            if not user_record.empty:
                st.session_state['user'] = user_record.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Login Failed.")

# --- EVALUATION PAGE ---
else:
    user = st.session_state['user']
    st.title(TITLE)
    st.markdown(CONFIDENTIALITY_TEXT)
    
    col1, col2 = st.columns([8,1])
    with col1: st.info(f"Logged in as: **{user['Student Name']}** (Group {user['Group #']})")
    with col2: 
        if st.button("Logout"):
            st.session_state['user'] = None
            st.rerun()
            
    df_students = load_students()
    group_members = df_students[df_students['Group #'] == user['Group #']]
    
    with st.form("eval_form"):
        st.write("Assign 0-100% for each criterion.")
        submission_data = []
        
        for idx, member in group_members.iterrows():
            st.markdown(f"--- \n ### Evaluating: {member['Student Name']}")
            cols = st.columns(len(CRITERIA) + 1)
            member_scores = []
            
            for i, criterion in enumerate(CRITERIA):
                with cols[i]:
                    score = st.number_input(criterion, min_value=0, max_value=100, value=0, step=5, key=f"{member['Student ID']}_{i}")
                    member_scores.append(score)
            
            avg = sum(member_scores) / len(member_scores) if member_scores else 0
            cols[-1].metric("AVG", f"{avg:.1f}%")
            
            row = {
                "Evaluator": user['Student Name'],
                "Evaluator ID": str(user['Student ID']),
                "Group": user['Group #'],
                "Peer Name": member['Student Name'],
                "Peer ID": str(member['Student ID']),
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Overall Score": avg
            }
            for i, cr in enumerate(CRITERIA): row[cr] = member_scores[i]
            submission_data.append(row)

        st.markdown("---")
        q1 = st.text_area("Comments (Low Score Given):")
        q2 = st.text_area("Comments (Low Score Received):")
        sig = st.text_input("Signature (Type Full Name):")
        
        if st.form_submit_button("Submit to Google Sheets"):
            if sig.lower().strip() != user['Student Name'].lower().strip():
                st.error("Signature mismatch.")
            else:
                for row in submission_data:
                    row["Comment (Low Score Given)"] = q1
                    row["Comment (Low Score Received)"] = q2
                    row["Signature"] = sig
                
                with st.spinner("Saving to Google Sheets..."):
                    success = save_to_google_sheets(user['Student ID'], submission_data)
                    if success:
                        st.success("Saved successfully! You may close the tab.")
                        st.balloons()

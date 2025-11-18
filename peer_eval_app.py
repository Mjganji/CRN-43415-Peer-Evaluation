import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION ---
ADMIN_PASSWORD = "ADMIN@1234$"  
STUDENT_FILE = "students.csv"
GOOGLE_SHEET_NAME = "Peer Evaluation Results" 

# --- UPDATED TEXT CONTENT ---
TITLE = "Self and Peer Evaluation Feedback Form - MECE 2310U"

CONFIDENTIALITY_TEXT = """
**This is a Self and Peer Evaluation Feedback Form for MECE 2310U-related Teamwork Activities that include: Biweekly Assignments #1, #2, and #3; one Case Study #1, #2 or #3; and Design Projects #1 and #2.**

**CONFIDENTIALITY:** This evaluation is a secret vote. Don’t show your vote to others, nor try to see or discuss others’ and yours votes. Please do not base your evaluations on friendship or personality conflicts. Your input is a valuable indicator to help assess contributions in a fair manner. 

**THESE EVALUATIONS WILL NOT BE PUBLISHED; YOUR IDENTITY WILL BE KEPT STRICTLY CONFIDENTIAL AND WILL BE NOT REVEALED IN ANY CIRCUMSTANCES.** **PLEASE USE ONLY THE LIGHT GREEN AREAS ON THE SHEET FOR YOUR FEEDBACK.**

**SUBMISSION DEADLINE:** The peer evaluation should be submitted within the timeframe presented below. No late submission of this form will be valid. If you submit this form late or do not submit it at all, that will be interpreted like you want to give 0% to yourself and 100% to all other team members. See the bottom of this document for more details.

**HOW THE EVALUATION WILL BE USED:** Your evaluations will be used to adjust your team members’ marks related to the course team work. The formula is: Overall Average Evaluation Score (per Individual) X Non-Adjusted Total Mark for Team-related coursework Obtained by the Group = Final Mark for team-related coursework (per Individual).
"""

MULTIPLE_ATTEMPT_TEXT = "Multiple submissions are allowed; only your most recent submission will be recorded and used for grading."

CRITERIA = [
    "Attendance at Meetings",
    "Meeting Deadlines",
    "Quality of Work",
    "Amount of Work",
    "Attitudes & Commitment"
]

# --- GOOGLE SHEETS CONNECTION (Fixed) ---
# We use cache_resource to hold the connection stable across re-runs
@st.cache_resource
def get_google_sheet_connection():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        s_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(
            s_info, scopes=scopes
        )
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        return None

def get_sheet():
    gc = get_google_sheet_connection()
    if gc:
        try:
            return gc.open(GOOGLE_SHEET_NAME).sheet1
        except Exception as e:
            st.error(f"Could not find the Sheet: {GOOGLE_SHEET_NAME}. Error: {e}")
            return None
    return None

# --- DATA FUNCTIONS ---
@st.cache_data
def load_students():
    try:
        df = pd.read_csv(STUDENT_FILE)
        df['Student ID'] = df['Student ID'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error loading student list: {e}")
        return None

def save_to_google_sheets(current_user_id, new_rows):
    sheet = get_sheet()
    if not sheet:
        st.error("Connection Error: Could not connect to Google Sheets.")
        return False
        
    try:
        # 1. Get all existing data
        try:
            all_data = sheet.get_all_records()
            df = pd.DataFrame(all_data)
        except:
            df = pd.DataFrame() 

        # 2. Filter out OLD entries from this user (Overwrite logic)
        if not df.empty and 'Evaluator ID' in df.columns:
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
            df = df[df['Evaluator ID'] != str(current_user_id)]
        
        # 3. Add the NEW data
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([df, new_df], ignore_index=True)
        
        # 4. Clear Sheet and Rewrite 
        sheet.clear()
        # Add headers
        if not final_df.empty:
            sheet.append_row(final_df.columns.tolist())
            sheet.append_rows(final_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# --- MAIN APP ---
st.set_page_config(page_title="Peer Evaluation", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("Teacher Access")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.success("Connected to Google Sheets")
        st.info("Check your Google Sheet named 'Peer Evaluation Results' to see live data.")
        
        if st.button("Calculate Grades Now"):
            sheet = get_sheet()
            if sheet:
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
                if not df.empty:
                    # Calculate average received score per student
                    summary = df.groupby('Peer Name')['Overall Score'].mean().reset_index()
                    summary.columns = ['Student Name', 'Average Received Score (%)']
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
                st.error("Login Failed: Name and Student Number do not match.")

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
        st.subheader("FIVE EVALUATION CRITERIA")
        st.write("Please assign 0-100% for each criterion to yourself and to all your group peers for their group work contributions as deserved.")
        st.caption(MULTIPLE_ATTEMPT_TEXT)
        
        submission_data = []
        
        for idx, member in group_members.iterrows():
            st.markdown(f"--- \n ### Evaluating: {member['Student Name']}")
            if member['Student Name'] == user['Student Name']:
                st.caption("(This is your Self-Evaluation)")

            cols = st.columns(len(CRITERIA) + 1)
            member_scores = []
            
            for i, criterion in enumerate(CRITERIA):
                with cols[i]:
                    score = st.number_input(criterion, min_value=0, max_value=100, value=0, step=5, key=f"{member['Student ID']}_{i}")
                    member_scores.append(score)
            
            avg = sum(member_scores) / len(member_scores) if member_scores else 0
            cols[-1].metric("OVERALL SCORE", f"{avg:.1f}%")
            
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
        st.subheader("Comments")
        
        q1 = st.text_area("If you have given 90% or less “overall average evaluation score” to one (or more) team members, please explain within the rectangle below why the particular team member (or members) deserve the low score. Please provide specific and objective reasons.")
        q2 = st.text_area("If you think you might get 90% or less \"overall average\" score by other members, please explain within the rectangle below why you would NOT deserve the low score. Please provide specific and objective reasons.")
        
        st.subheader("Signature")
        sig = st.text_input("Signature (Just print name is enough):")
        
        submitted = st.form_submit_button("Submit to Google Sheets")
        
        if submitted:
            # No validation check on signature anymore
            for row in submission_data:
                row["Comment (Low Score Given)"] = q1
                row["Comment (Low Score Received)"] = q2
                row["Signature"] = sig
            
            with st.spinner("Saving to Google Sheets..."):
                success = save_to_google_sheets(user['Student ID'], submission_data)
                if success:
                    st.success("Saved successfully! You may close the tab.")
                    st.balloons()

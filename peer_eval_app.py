import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import smtplib
import ssl
from email.message import EmailMessage
import random
import time

# --- CONFIGURATION ---
STUDENT_FILE = "students.csv"
GOOGLE_SHEET_NAME = "Peer Evaluation Results"

# --- TEXT CONTENT ---
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

# --- EMAIL / OTP FUNCTIONS ---
def send_otp_email(to_email, otp_code):
    try:
        email_secrets = st.secrets["email"]
        sender_email = email_secrets["sender_email"]
        sender_password = email_secrets["sender_password"]
        smtp_server = email_secrets["smtp_server"]
        smtp_port = email_secrets["smtp_port"]

        msg = EmailMessage()
        msg.set_content(f"Your Verification Code for Peer Evaluation is: {otp_code}\n\nThis code expires in 1 hour.")
        msg["Subject"] = "Peer Evaluation Access Code"
        msg["From"] = sender_email
        msg["To"] = to_email

        # Context for SSL
        context = ssl.create_default_context()

        # Connect and send
        # Logic handles both SSL (465) and STARTTLS (587)
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender_email, sender_password)
                server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_google_sheet_connection():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets not found!")
            return None
            
        s_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(
            s_info, scopes=scopes
        )
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

def get_sheet():
    gc = get_google_sheet_connection()
    if not gc: return None
    try:
        return gc.open(GOOGLE_SHEET_NAME).sheet1
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# --- DATA FUNCTIONS ---
@st.cache_data
def load_students():
    try:
        df = pd.read_csv(STUDENT_FILE)
        df['Student ID'] = df['Student ID'].astype(str)
        # Clean up column names (strip spaces)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading student list: {e}")
        return None

def save_to_google_sheets(current_user_id, new_rows):
    sheet = get_sheet()
    if not sheet: return False
    try:
        try:
            all_data = sheet.get_all_records()
            df = pd.DataFrame(all_data)
        except:
            df = pd.DataFrame() 

        # Overwrite logic
        if not df.empty and 'Evaluator ID' in df.columns:
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
            df = df[df['Evaluator ID'] != str(current_user_id)]
        
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([df, new_df], ignore_index=True)
        
        sheet.clear()
        if not final_df.empty:
            sheet.append_row(final_df.columns.tolist())
            sheet.append_rows(final_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# --- MAIN APP ---
st.set_page_config(page_title="Peer Evaluation", layout="wide")

# Custom CSS for Score Box
st.markdown("""
<style>
    .score-box {
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 20px;
        margin-top: 25px;
        color: white;
    }
    .score-green { background-color: #28a745; }
    .score-red { background-color: #dc3545; } 
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'otp_sent' not in st.session_state:
    st.session_state['otp_sent'] = False
if 'otp_code' not in st.session_state:
    st.session_state['otp_code'] = None
if 'otp_expiry' not in st.session_state:
    st.session_state['otp_expiry'] = None
if 'selected_student_data' not in st.session_state:
    st.session_state['selected_student_data'] = None

# --- LOGIN FLOW (OTP) ---
if st.session_state['user'] is None:
    st.title(TITLE)
    st.subheader("Step 1: Secure Login")
    
    df_students = load_students()
    
    if df_students is not None:
        # STAGE 1: Select Name
        if not st.session_state['otp_sent']:
            names = sorted(df_students['Student Name'].unique().tolist())
            selected_name = st.selectbox("Select your name:", [""] + names)
            
            if st.button("Send Verification Code"):
                if selected_name:
                    # Find email
                    student_record = df_students[df_students['Student Name'] == selected_name]
                    if not student_record.empty:
                        if 'Email' not in student_record.columns:
                            st.error("Error: 'Email' column not found in student database.")
                        else:
                            email_addr = student_record.iloc[0]['Email']
                            
                            # Generate OTP
                            otp = str(random.randint(100000, 999999))
                            expiry = datetime.now() + timedelta(hours=1)
                            
                            # Store in session
                            st.session_state['otp_code'] = otp
                            st.session_state['otp_expiry'] = expiry
                            st.session_state['selected_student_data'] = student_record.iloc[0].to_dict()
                            
                            # Send Email
                            with st.spinner(f"Sending code to {email_addr}..."):
                                if send_otp_email(email_addr, otp):
                                    st.session_state['otp_sent'] = True
                                    st.success(f"Code sent to {email_addr}. Check your inbox (and spam).")
                                    st.rerun()
                    else:
                        st.error("Student not found.")
                else:
                    st.warning("Please select a name.")
        
        # STAGE 2: Verify OTP
        else:
            st.info(f"Code sent to your email. It expires in 1 hour.")
            
            otp_input = st.text_input("Enter the 6-digit code:", max_chars=6)
            
            col1, col2 = st.columns([1,1])
            with col1:
                if st.button("Login"):
                    current_time = datetime.now()
                    saved_otp = st.session_state['otp_code']
                    expiry_time = st.session_state['otp_expiry']
                    
                    if otp_input == saved_otp:
                        if current_time < expiry_time:
                            st.session_state['user'] = st.session_state['selected_student_data']
                            st.success("Login Successful!")
                            st.rerun()
                        else:
                            st.error("Code expired. Please start over.")
                            if st.button("Start Over"):
                                st.session_state['otp_sent'] = False
                                st.rerun()
                    else:
                        st.error("Invalid Code.")
            
            with col2:
                if st.button("Resend / Change Name"):
                    st.session_state['otp_sent'] = False
                    st.session_state['otp_code'] = None
                    st.rerun()

# --- EVALUATION FORM (LIVE MODE) ---
else:
    user = st.session_state['user']
    st.title(TITLE)
    st.markdown(CONFIDENTIALITY_TEXT)
    
    col1, col2 = st.columns([8,1])
    with col1: st.info(f"Logged in as: **{user['Student Name']}** (Group {user['Group #']})")
    with col2: 
        if st.button("Logout"):
            st.session_state['user'] = None
            st.session_state['otp_sent'] = False
            st.rerun()
            
    df_students = load_students()
    group_members = df_students[df_students['Group #'] == user['Group #']]
    
    st.subheader("FIVE EVALUATION CRITERIA")
    st.write("Assign 0-100% for each criterion. **Press Enter/Tab after typing to update the total.**")
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
                score = st.number_input(
                    criterion, 
                    min_value=0, max_value=100, value=0, step=5, 
                    key=f"{member['Student ID']}_{i}"
                )
                if score < 80:
                    st.markdown(":red[⚠️ **< 80%**]")
                member_scores.append(score)
        
        avg = sum(member_scores) / len(member_scores) if member_scores else 0
        
        # Standard Metric Box
        with cols[-1]:
            st.metric(label="OVERALL SCORE", value=f"{avg:.1f}%")
        
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
    
    q1 = st.text_area("If you gave 90% or less to anyone, please explain why:")
    q2 = st.text_area("If you expect 90% or less from others, please explain why:")
    
    st.subheader("Signature")
    sig = st.text_input("Signature (Just print name is enough):")
    
    st.write("") 
    
    if st.button("Submit to Google Sheets", type="primary"):
        for row in submission_data:
            row["Comment (Low Score Given)"] = q1
            row["Comment (Low Score Received)"] = q2
            row["Signature"] = sig
        
        with st.spinner("Saving..."):
            success = save_to_google_sheets(user['Student ID'], submission_data)
            if success:
                st.success("Saved successfully!")
                st.balloons()

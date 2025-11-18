import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION ---
ADMIN_PASSWORD = "ADMIN@1234$"
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

        if not df.empty and 'Evaluator ID' in df.columns:
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
            df = df[df['Evaluator ID'] != str(current_user_id)]
        
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([df, new_df], ignore_index=True)
        
        sheet.clear()
        if not final_df.empty:
            sheet.append_row(final_

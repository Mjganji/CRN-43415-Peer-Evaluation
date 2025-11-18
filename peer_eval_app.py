import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURATION ---
ADMIN_PASSWORD = "TeacherPassword123"  # <--- Update this password
STUDENT_FILE = "students.csv"
RESULTS_FILE = "peer_eval_data.csv"

# --- TEXT & CRITERIA ---
TITLE = "Self and Peer Evaluation Feedback Form - MECE 2310U"
CONFIDENTIALITY_TEXT = """
**CONFIDENTIALITY:** This evaluation is a secret vote. Don’t show your vote to others, nor try to see or discuss others’ and yours votes. 
Please do not base your evaluations on friendship or personality conflicts. Your input is a valuable indicator to help assess contributions in a fair manner. 
**THESE EVALUATIONS WILL NOT BE PUBLISHED; YOUR IDENTITY WILL BE KEPT STRICTLY CONFIDENTIAL.**
"""

CRITERIA = [
    "Attendance at Meetings",
    "Meeting Deadlines",
    "Quality of Work",
    "Amount of Work",
    "Attitudes & Commitment"
]

# --- FUNCTIONS ---
@st.cache_data
def load_students():
    try:
        df = pd.read_csv(STUDENT_FILE)
        df['Student ID'] = df['Student ID'].astype(str) # Ensure IDs are strings
        return df
    except Exception as e:
        st.error(f"Error loading student list: {e}")
        return None

def save_submission_overwrite(evaluator_id, new_data_rows):
    """
    Reads the existing CSV, removes any rows matching the current Evaluator ID,
    and appends the new data. This ensures only the latest attempt is kept.
    """
    # 1. Load existing data or create empty DataFrame
    if os.path.exists(RESULTS_FILE):
        try:
            df = pd.read_csv(RESULTS_FILE)
            # Ensure IDs are strings for comparison
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
        except pd.errors.EmptyDataError:
             df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    # 2. Filter out OLD entries from this specific student (if any exist)
    if not df.empty and 'Evaluator ID' in df.columns:
        # Keep only rows that are NOT from this student
        df = df[df['Evaluator ID'] != str(evaluator_id)]

    # 3. Create DataFrame from the NEW submission
    new_df = pd.DataFrame(new_data_rows)

    # 4. Combine and Save
    final_df = pd.concat([df, new_df], ignore_index=True)
    final_df.to_csv(RESULTS_FILE, index=False)

def get_results():
    if os.path.exists(RESULTS_FILE):
        return pd.read_csv(RESULTS_FILE)
    return pd.DataFrame()

# --- MAIN APP ---
st.set_page_config(page_title="Peer Evaluation", layout="wide")

# Session State for Login
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- SIDEBAR: ADMIN LOGIN ---
with st.sidebar:
    st.header("Admin / Teacher Access")
    admin_pass = st.text_input("Admin Password", type="password")
    if admin_pass == ADMIN_PASSWORD:
        st.success("Admin Access Granted")
        st.divider()
        st.subheader("Data Management")
        
        results_df = get_results()
        if not results_df.empty:
            st.write(f"Total Response Rows: {len(results_df)}")
            st.info("Note: If a student resubmits, their old rows are overwritten automatically.")
            
            # 1. Download Raw Data
            st.download_button(
                label="Download Raw Responses (CSV)",
                data=results_df.to_csv(index=False),
                file_name="raw_peer_evaluations.csv",
                mime="text/csv"
            )
            
            # 2. Calculate Summary Scores (The Formula)
            if st.button("Calculate Student Averages"):
                st.write("### Calculated Scores (Received from Peers)")
                try:
                    # Group by 'Peer Name' (the person being graded) and average the 'Overall Score'
                    summary = results_df.groupby('Peer Name')['Overall Score'].mean().reset_index()
                    summary.columns = ['Student Name', 'Average Received Score (%)']
                    st.dataframe(summary)
                    
                    st.download_button(
                        label="Download Summary Grades",
                        data=summary.to_csv(index=False),
                        file_name="summary_grades.csv",
                        mime="text/csv"
                    )
                except KeyError:
                    st.error("Not enough data to calculate yet.")
        else:
            st.info("No responses submitted yet.")

# --- PAGE 1: STUDENT LOGIN ---
if st.session_state['user'] is None:
    st.title(TITLE)
    st.subheader("Step 1: Identification")
    
    df_students = load_students()
    
    if df_students is not None:
        # Name Selection
        names = sorted(df_students['Student Name'].unique().tolist())
        selected_name = st.selectbox("Select your name:", [""] + names)
        
        # Password (ID)
        student_id = st.text_input("Enter your Student Number (Password):", type="password")
        
        if st.button("Login"):
            # VALIDATION LOGIC
            user_record = df_students[
                (df_students['Student Name'] == selected_name) & 
                (df_students['Student ID'] == student_id)
            ]
            
            if not user_record.empty:
                st.session_state['user'] = user_record.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Access Denied: Student Number does not match the selected Name.")

# --- PAGE 2: EVALUATION FORM ---
else:
    user = st.session_state['user']
    df_students = load_students()
    
    st.title(TITLE)
    st.markdown(CONFIDENTIALITY_TEXT)
    
    # Add Logout button in top corner
    col1, col2 = st.columns([8,1])
    with col1:
        st.info(f"Logged in as: **{user['Student Name']}** (Group {user['Group #']})")
    with col2:
        if st.button("Logout"):
            st.session_state['user'] = None
            st.rerun()
    
    # Get Group Members
    group_members = df_students[df_students['Group #'] == user['Group #']]
    
    with st.form("eval_form"):
        st.subheader("Five Evaluation Criteria (0-100%)")
        st.write("Assign 0-100% for each criterion to yourself and your group peers.")
        st.warning("Note: You can submit this form multiple times. The most recent submission will overwrite your previous one.")
        
        submission_data = []
        
        # Create a dynamic table for each member
        for idx, member in group_members.iterrows():
            st.markdown(f"--- \n ### Evaluating: {member['Student Name']}")
            if member['Student Name'] == user['Student Name']:
                st.caption("(This is your Self-Evaluation)")
            
            cols = st.columns(len(CRITERIA) + 1) # +1 for the Average column
            
            member_scores = []
            for i, criterion in enumerate(CRITERIA):
                with cols[i]:
                    score = st.number_input(
                        label=criterion,
                        min_value=0, max_value=100, value=0, step=5,
                        key=f"{member['Student ID']}_{i}" 
                    )
                    member_scores.append(score)
            
            # Calculate Average on the fly
            avg_score = sum(member_scores) / len(member_scores) if member_scores else 0
            with cols[-1]:
                st.metric(label="OVERALL AVG", value=f"{avg_score:.1f}%")
            
            # Prepare data row
            row = {
                "Evaluator": user['Student Name'],
                "Evaluator ID": str(user['Student ID']), # Store as string
                "Group": user['Group #'],
                "Peer Name": member['Student Name'],
                "Peer ID": str(member['Student ID']),
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Overall Score": avg_score
            }
            # Add individual criterion scores
            for i, criterion in enumerate(CRITERIA):
                row[criterion] = member_scores[i]
            
            submission_data.append(row)

        st.markdown("---")
        st.subheader("Comments")
        
        q1 = st.text_area("If you have given 90% or less 'overall average' to any member, please explain why (specific reasons):")
        q2 = st.text_area("If you think you might get 90% or less from others, please explain why you would NOT deserve the low score:")
        
        st.subheader("Signature")
        signature = st.text_input("Please type your full name to sign:")
        
        submitted = st.form_submit_button("Submit Evaluation")
        
        if submitted:
            if signature.lower().strip() != user['Student Name'].lower().strip():
                st.error("Signature mismatch. Please type your exact name as it appears in the login.")
            else:
                # Add common fields to all rows
                for row in submission_data:
                    row["Comment (Low Score Given)"] = q1
                    row["Comment (Low Score Received)"] = q2
                    row["Signature"] = signature
                
                # SAVE: Calls the new Overwrite function
                save_submission_overwrite(user['Student ID'], submission_data)
                
                st.success("Success! Your evaluation has been recorded (previous attempts were overwritten).")
                st.balloons()
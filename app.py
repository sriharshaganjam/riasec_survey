import streamlit as st

# MUST BE FIRST - before ANY other Streamlit commands
st.set_page_config(page_title="RIASEC Survey", layout="wide")

# Now import everything else
import pandas as pd
import json
import uuid
from datetime import datetime, UTC
import plotly.graph_objects as go

from google.oauth2.service_account import Credentials
import gspread
from gspread.exceptions import WorksheetNotFound, APIError, GSpreadException

# -------------------------
# QUESTIONS (Q1..Q42)
# -------------------------
QUESTIONS = [
    (1, "Q1. I like to work on cars", 'R'),
    (2, "Q2. I like to do puzzles", 'I'),
    (3, "Q3. I am good at working independently", 'A'),
    (4, "Q4. I like to work in teams", 'S'),
    (5, "Q5. I am an ambitious person, I set goals for myself", 'E'),
    (6, "Q6. I like to organize things, (files, desks/offices)", 'C'),
    (7, "Q7. I like to build things", 'R'),
    (8, "Q8. I like to read about art and music", 'A'),
    (9, "Q9. I like to have clear instructions to follow", 'C'),
    (10, "Q10. I like to try to influence or persuade people", 'E'),
    (11, "Q11. I like to do experiments", 'I'),
    (12, "Q12. I like to teach or train people", 'S'),
    (13, "Q13. I like trying to help people solve their problems", 'S'),
    (14, "Q14. I like to take care of animals", 'R'),
    (15, "Q15. I wouldn't mind working 8 hours per day in an office", 'C'),
    (16, "Q16. I like selling things", 'E'),
    (17, "Q17. I enjoy creative writing", 'A'),
    (18, "Q18. I enjoy science", 'I'),
    (19, "Q19. I am quick to take on new responsibilities", 'E'),
    (20, "Q20. I am interested in healing people", 'S'),
    (21, "Q21. I enjoy trying to figure out how things work", 'I'),
    (22, "Q22. I like putting things together or assembling things", 'R'),
    (23, "Q23. I am a creative person", 'A'),
    (24, "Q24. I pay attention to details", 'C'),
    (25, "Q25. I like to do filing or typing", 'C'),
    (26, "Q26. I like to analyze things (problems/ situations)", 'I'),
    (27, "Q27. I like to play instruments or sing", 'A'),
    (28, "Q28. I enjoy learning about other cultures", 'S'),
    (29, "Q29. I would like to start my own business", 'E'),
    (30, "Q30. I like to cook", 'R'),
    (31, "Q31. I like acting in plays", 'A'),
    (32, "Q32. I am a practical person", 'R'),
    (33, "Q33. I like working with numbers or charts", 'I'),
    (34, "Q34. I like to get into discussions about issues", 'S'),
    (35, "Q35. I am good at keeping records of my work", 'C'),
    (36, "Q36. I like to lead", 'E'),
    (37, "Q37. I like working outdoors", 'R'),
    (38, "Q38. I would like to work in an office", 'C'),
    (39, "Q39. I'm good at math", 'I'),
    (40, "Q40. I like helping people", 'S'),
    (41, "Q41. I like to draw", 'A'),
    (42, "Q42. I like to give speeches", 'E'),
]
TRAITS = ['R', 'I', 'A', 'S', 'E', 'C']

# -------------------------
# COURSES (30 titles)
# -------------------------
COURSES = [
    "ENVIRONMENTAL STUDIES",
    "CLASSICAL MECHANICS",
    "HUMAN RESOURCE MANAGEMENT",
    "FUNDAMENTALS OF ARTIFICIAL INTELLIGENCE",
    "COMPUTER AIDED DESIGN (CAD)",
    "BIOTECHNOLOGY",
    "ORGANIC CHEMISTRY",
    "ZOOLOGY",
    "PYTHON PROGRAMMING",
    "BUSINESS ECONOMICS",
    "INTERIOR DESIGN",
    "LANGUAGE STUDIES",
    "CLAY MODELING",
    "GRAPHIC DESIGN",
    "PAINTING",
    "FUNDAMENTALS OF ADVERTISING",
    "MARKETING MANAGEMENT",
    "TALENT ACQUISITION",
    "SOCIOLOGY",
    "BASIC PSYCHOLOGY",
    "POLITICAL SCIENCE",
    "BANKING AUDIT AND ASSURANCE",
    "ENTREPRENEURSHIP AND FASHION MERCHENDISING",
    "BUSINESS LAW",
    "FINANCIAL TRADES AND MARKET RESEARCH",
    "FINANCIAL REPORTING STATEMENT AND ANALYSIS",
    "TRAVEL & TOUR OPERATIONS",
    "BUSINESS DATA ANALYSIS",
    "JOURNALISM",
    "WEALTH MANAGEMENT"
]

# -------------------------
# Google Sheets helpers
# -------------------------
GS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gspread_client_from_secrets():
    try:
        sa_info = st.secrets["gcp_service_account"]
        if isinstance(sa_info, str):
            sa_info = json.loads(sa_info)
        spreadsheet_id = st.secrets["sheet"]["spreadsheet_id"]
        credentials = Credentials.from_service_account_info(sa_info, scopes=GS_SCOPES)
        gc = gspread.authorize(credentials)
        _ = gc.open_by_key(spreadsheet_id)
        return gc, spreadsheet_id
    except Exception as exc:
        st.error(f"Google Sheets connection failed: {type(exc).__name__}: {str(exc)}")
        return None, None

@st.cache_resource
def get_spreadsheet(_gc, spreadsheet_id):
    return _gc.open_by_key(spreadsheet_id)

def ensure_sheet_structure_and_headers(gc, spreadsheet_id):
    sh = get_spreadsheet(gc, spreadsheet_id)

    # submissions header - updated to include consent checkboxes
    desired_sub_headers = [
        "submission_id", "student_name", "degree", "email", "timestamp",
        "consent_purpose", "consent_confidentiality", "consent_participate",
        "consent_timestamp"
    ]
    try:
        sub_ws = sh.worksheet("submissions")
        current_headers = sub_ws.row_values(1)
        if current_headers != desired_sub_headers:
            if len(current_headers) > 0:
                sub_ws.delete_rows(1)
            sub_ws.insert_row(desired_sub_headers, index=1)
    except WorksheetNotFound:
        sub_ws = sh.add_worksheet(title="submissions", rows="2000", cols="20")
        sub_ws.append_row(desired_sub_headers)

    # answers header
    try:
        ans_ws = sh.worksheet("answers")
        hdr = ans_ws.row_values(1)
        if hdr != ["submission_id", "question_id", "trait", "answer"]:
            if len(hdr) > 0:
                ans_ws.delete_rows(1)
            ans_ws.insert_row(["submission_id", "question_id", "trait", "answer"], index=1)
    except WorksheetNotFound:
        ans_ws = sh.add_worksheet(title="answers", rows="5000", cols="10")
        ans_ws.append_row(["submission_id", "question_id", "trait", "answer"])

    # scores header
    try:
        scores_ws = sh.worksheet("scores")
        hdr = scores_ws.row_values(1)
        desired_scores_hdr = ["submission_id","R_percent","I_percent","A_percent","S_percent","E_percent","C_percent"]
        if hdr != desired_scores_hdr:
            if len(hdr) > 0:
                scores_ws.delete_rows(1)
            scores_ws.insert_row(desired_scores_hdr, index=1)
    except WorksheetNotFound:
        scores_ws = sh.add_worksheet(title="scores", rows="2000", cols="20")
        scores_ws.append_row(["submission_id","R_percent","I_percent","A_percent","S_percent","E_percent","C_percent"])

    # choices header
    desired_choices_hdr = ["submission_id"] + COURSES
    try:
        choices_ws = sh.worksheet("choices")
        hdr = choices_ws.row_values(1)
        if hdr != desired_choices_hdr:
            if len(hdr) > 0:
                choices_ws.delete_rows(1)
            choices_ws.insert_row(desired_choices_hdr, index=1)
    except WorksheetNotFound:
        choices_ws = sh.add_worksheet(title="choices", rows="2000", cols=max(10, len(desired_choices_hdr)))
        choices_ws.append_row(desired_choices_hdr)

    return sh

def append_submission_answers_scores(gc, spreadsheet_id, submission_id, student_name, degree, email, 
                                     timestamp, consent_purpose, consent_confidentiality, 
                                     consent_participate, consent_timestamp, answers, scores_df):
    try:
        sh = ensure_sheet_structure_and_headers(gc, spreadsheet_id)
        sub_ws = sh.worksheet("submissions")
        ans_ws = sh.worksheet("answers")
        scores_ws = sh.worksheet("scores")

        sub_ws.append_row([
            submission_id, student_name, degree, email, timestamp,
            str(consent_purpose), str(consent_confidentiality), 
            str(consent_participate), consent_timestamp
        ])

        rows = [[submission_id, qid, trait, ans] for qid, trait, ans in answers]
        if rows:
            ans_ws.append_rows(rows, value_input_option="USER_ENTERED")

        pct_map = {row['trait']: float(row['score_percent']) for _, row in scores_df.iterrows()}
        score_row = [
            submission_id,
            f"{pct_map.get('R', 0):.1f}",
            f"{pct_map.get('I', 0):.1f}",
            f"{pct_map.get('A', 0):.1f}",
            f"{pct_map.get('S', 0):.1f}",
            f"{pct_map.get('E', 0):.1f}",
            f"{pct_map.get('C', 0):.1f}",
        ]
        scores_ws.append_row(score_row, value_input_option="USER_ENTERED")
        return True, None
    except (APIError, GSpreadException) as e:
        return False, f"Google Sheets API error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def append_choices_row(gc, spreadsheet_id, submission_id, selected_bool_list):
    try:
        sh = ensure_sheet_structure_and_headers(gc, spreadsheet_id)
        choices_ws = sh.worksheet("choices")
        row = [submission_id] + [1 if b else 0 for b in selected_bool_list]
        choices_ws.append_row(row, value_input_option="USER_ENTERED")
        return True, None
    except (APIError, GSpreadException) as e:
        return False, f"Google Sheets API error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

# -------------------------
# Scoring & chart helpers
# -------------------------
def compute_standardized_scores(answers_df):
    df = answers_df.copy()
    df['answer'] = df['answer'].astype(int)
    trait_yes = df.groupby('trait')['answer'].sum().reindex(TRAITS).fillna(0).astype(int)
    trait_n = df.groupby('trait')['answer'].count().reindex(TRAITS).fillna(0).astype(int)
    props = (trait_yes / trait_n.replace(0, 1)).round(6)
    props = props.where(trait_n > 0, 0)
    denom = props.sum()
    if denom == 0:
        scores = pd.Series([0]*len(TRAITS), index=TRAITS)
    else:
        scores = (props / denom).round(6)
    return pd.DataFrame({
        "trait": TRAITS,
        "yes_count": trait_yes.values,
        "n_items": trait_n.values,
        "prop": props.values,
        "score_frac": scores.values,
        "score_percent": (scores.values * 100).round(1)
    })

def make_radar_chart(scores_df, title="RIASEC Profile"):
    traits = scores_df['trait'].tolist()
    values = scores_df['score_percent'].tolist()
    traits_closed = traits + [traits[0]]
    values_closed = values + [values[0]]
    max_value = max(values) if max(values) > 0 else 100
    range_max = min(100, max_value * 1.2)
    labels = [f"{v:.1f}%" for v in values]
    labels_closed = labels + [labels[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=traits_closed,
        fill='toself',
        name='Percent',
        line=dict(width=3),
        mode='lines+markers+text',
        text=labels_closed,
        textposition='top center',
        hovertemplate='%{theta}: %{r:.1f}%<extra></extra>'
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, range_max], tickformat=".0f")),
        showlegend=False,
        title=title,
        height=650,
        margin=dict(l=30, r=30, t=80, b=30)
    )
    return fig

# -------------------------
# Session state initialization
# -------------------------
if 'course_checks' not in st.session_state or len(st.session_state.course_checks) != len(COURSES):
    st.session_state.course_checks = [False] * len(COURSES)

for qid, _, _ in QUESTIONS:
    key = f"q_{qid}"
    if key not in st.session_state:
        st.session_state[key] = "—"

# Initialize consent checkboxes
if 'consent_purpose' not in st.session_state:
    st.session_state.consent_purpose = False
if 'consent_confidentiality' not in st.session_state:
    st.session_state.consent_confidentiality = False
if 'consent_participate' not in st.session_state:
    st.session_state.consent_participate = False

# -------------------------
# Main UI
# -------------------------
st.title("RIASEC Survey")

gc, spreadsheet_id = get_gspread_client_from_secrets()
if not gc:
    st.error("Google Sheets not configured or secrets missing. Please fix st.secrets.")
    st.stop()

# -------------------------
# CONSENT FORM SECTION
# -------------------------
st.header("Informed Consent")

st.subheader("Title of the Study: Assessing Student Vocational Interests Using The RIASEC Framework")
st.markdown("**Principal Investigator/Administrator:** sriharsha.g@jainuniversity.ac.in")

st.markdown("### Purpose Statement:")
st.markdown("""
The purpose of this survey is to understand individual vocational interests, preferences, and
personality orientations using the RIASEC (Realistic, Investigative, Artistic, Social, Enterprising,
Conventional) model. This information will be used for research, career guidance, and
developmental feedback purposes only. Your participation in this survey is voluntary. You may 
choose to withdraw at any time without any negative consequences. The estimated time to complete 
the survey is approximately 10–15 minutes. Your participation in this survey may help you gain 
insights into your vocational interests and possible career pathways aligned with your personal 
strengths and preferences.
""")

consent_purpose = st.checkbox(
    "I understand the purpose of this study and survey",
    key="consent_purpose_check",
    value=st.session_state.consent_purpose
)
st.session_state.consent_purpose = consent_purpose

st.markdown("### Confidentiality Statement:")
st.markdown("""
All responses will be treated with strict confidentiality. Data will be stored securely and analyzed
only in aggregated form. No personally identifiable information will be disclosed in reports or
publications arising from this study.
""")

consent_confidentiality = st.checkbox(
    "I understand the confidential implications of this survey",
    key="consent_confidentiality_check",
    value=st.session_state.consent_confidentiality
)
st.session_state.consent_confidentiality = consent_confidentiality

st.markdown("### Consent Statement:")
st.markdown("""
By proceeding with this survey, you acknowledge that you have read and understood the above
information and voluntarily consent to participate in this RIASEC-based study.
""")

consent_participate = st.checkbox(
    "I agree to participate voluntarily in this survey",
    key="consent_participate_check",
    value=st.session_state.consent_participate
)
st.session_state.consent_participate = consent_participate

# Check if all consent checkboxes are checked
all_consents_given = consent_purpose and consent_confidentiality and consent_participate

if not all_consents_given:
    st.warning("⚠️ Please check all three consent boxes above to proceed with the survey.")
    st.stop()

st.success("✅ Consent received. You may now proceed with the survey.")
st.markdown("---")

# -------------------------
# SURVEY SECTION (enabled only after consent)
# -------------------------
st.markdown("**Note:** All questions are mandatory. Please choose either a 'YES' or a 'NO' for the below questions")

# Basic fields
name = st.text_input("Student name", key="name_input")
degree = st.text_input("Current Enrolled Degree (e.g., B.Sc Computer Science)", key="degree_input")
email = st.text_input("Email (optional)", key="email_input")

st.markdown("---")
st.markdown("Select **Yes** or **No** for each statement. Default is blank — you must choose.")

# Questions
answers = []
for qid, text, trait in QUESTIONS:
    choice = st.radio(f"{text}", options=["—", "Yes", "No"], index=0, key=f"q_{qid}", horizontal=True)
    val = 1 if choice == "Yes" else 0 if choice == "No" else None
    answers.append((qid, trait, val))

# Courses block
st.markdown("### THOUGHT EXPERIMENT ON CHOICE")
st.markdown("**If you have a chance to pick 7 courses to study, purely based on your interest & passion what courses would you like to study?**")
st.markdown("1. A max of 7 selections is allowed.\n2. Please be candid in your response.\n3. The selection has to be only based on your interest and passion, so it's ok to choose a course even if you have no prior experience in that course.")
st.markdown("---")

cols = st.columns(3)
for col_idx, col in enumerate(cols):
    with col:
        start = col_idx * 10
        end = min(start + 10, len(COURSES))
        for i in range(start, end):
            checked = st.checkbox(COURSES[i], key=f"course_{i}", value=st.session_state.course_checks[i])
            st.session_state.course_checks[i] = checked

selected_count = sum(1 for v in st.session_state.course_checks if v)
st.markdown(f"**Selected:** {selected_count} / 7")
if selected_count > 7:
    over = selected_count - 7
    st.error(f"You selected {selected_count} courses — the maximum allowed is 7. Please uncheck {over} course(s).")

# Validation
missing_qs = [f"Q{qid}" for qid, trait, val in answers if val is None]
all_questions_answered = (len(missing_qs) == 0)
basic_info_ok = bool(name.strip()) and bool(degree.strip())
submit_enabled = basic_info_ok and all_questions_answered and (0 <= selected_count <= 7)

if not basic_info_ok:
    st.info("Please enter your name and your current enrolled degree.")
if missing_qs:
    st.info(f"Please answer all questions. Missing: {', '.join(missing_qs)}")
if selected_count == 0:
    st.info("Please select up to 7 courses (you may select none if you prefer).")
if selected_count > 7:
    st.info("Reduce your selected courses to at most 7 to enable Submit.")

# Submit button
if st.button("Submit", disabled=not submit_enabled):
    if not basic_info_ok:
        st.error("Please fill Name and Degree.")
    elif missing_qs:
        st.error("Please answer all questions before submitting.")
    elif selected_count > 7:
        st.error(f"Too many selections ({selected_count}) — please select at most 7.")
    else:
        answers_df = pd.DataFrame(answers, columns=["question_id", "trait", "answer"])
        scores_df = compute_standardized_scores(answers_df)

        submission_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        consent_timestamp = timestamp

        ok, err = append_submission_answers_scores(
            gc, spreadsheet_id, submission_id, name.strip(), degree.strip(), 
            email.strip(), timestamp, 
            st.session_state.consent_purpose,
            st.session_state.consent_confidentiality,
            st.session_state.consent_participate,
            consent_timestamp, answers, scores_df
        )
        if not ok:
            st.error(err)
        else:
            ok2, err2 = append_choices_row(gc, spreadsheet_id, submission_id, st.session_state.course_checks)
            if not ok2:
                st.error(err2)
            else:
                st.success("✅ Submission saved to Google Sheets (submissions, answers, scores, choices).")
                
                st.markdown("---")
                st.subheader("Thank you for participating in the RIASEC Vocational Interest Survey.")
                
                st.markdown("""
                <div style="border: 2px solid #cccccc; padding: 20px; border-radius: 5px; margin: 20px 0;">
                This assessment is designed to identify your primary vocational interest types among six categories:<br><br>
                • <b>Realistic (R):</b> Hands-on, practical, and mechanical work.<br>
                • <b>Investigative (I):</b> Analytical, intellectual, and research-oriented roles.<br>
                • <b>Artistic (A):</b> Creative, expressive, and design-oriented activities.<br>
                • <b>Social (S):</b> Helping, teaching, or service-oriented careers.<br>
                • <b>Enterprising (E):</b> Persuasive, leadership, and business-focused roles.<br>
                • <b>Conventional (C):</b> Structured, detail-oriented, and data-driven work.<br><br>
                Your scores reflect your preferences, not your abilities or limitations. There are no "right" or "wrong" answers in this assessment. The results will assist in identifying environments and tasks where you are most likely to find satisfaction and success.
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("### Your RIASEC Profile")
                display_df = scores_df.set_index("trait")[["yes_count", "n_items", "prop", "score_percent"]].rename(columns={"prop":"proportion","score_percent":"standardized_percent"})
                st.table(display_df)
                st.plotly_chart(make_radar_chart(scores_df), use_container_width=True)
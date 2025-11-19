import streamlit as st

# MUST BE FIRST - before ANY other Streamlit commands
st.set_page_config(page_title="RIASEC Survey", layout="wide")

# Now import everything else
import pandas as pd
import json
import uuid
from datetime import datetime, UTC
import plotly.graph_objects as go
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from google.oauth2.service_account import Credentials
import gspread
from gspread.exceptions import WorksheetNotFound, APIError, GSpreadException

# -------------------------
# CONFETTI CSS & ANIMATION
# -------------------------
CONFETTI_CSS = """
<style>
@keyframes confetti-fall {
    0% { transform: translateY(-100vh) rotate(0deg); opacity: 1; }
    100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
}

.confetti {
    position: fixed;
    width: 10px;
    height: 10px;
    top: -10px;
    z-index: 9999;
    animation: confetti-fall 3s linear forwards;
}

.confetti-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 9999;
}

.sticky-progress {
    position: sticky;
    top: 0;
    z-index: 999;
    background-color: white;
    padding: 20px 0;
    margin-bottom: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>
"""

def generate_confetti():
    """Generate confetti animation HTML"""
    import random
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#6c5ce7', '#a29bfe', '#fd79a8', '#fdcb6e']
    confetti_html = '<div class="confetti-container">'
    
    for i in range(50):
        left = random.randint(0, 100)
        delay = random.uniform(0, 2)
        duration = random.uniform(2, 4)
        color = random.choice(colors)
        confetti_html += f'<div class="confetti" style="left: {left}%; background-color: {color}; animation-delay: {delay}s; animation-duration: {duration}s;"></div>'
    
    confetti_html += '</div>'
    return CONFETTI_CSS + confetti_html

# -------------------------
# PROGRESS BAR STYLING
# -------------------------
PROGRESS_CSS = """
<style>
.progress-container {
    width: 100%;
    background-color: #e0e0e0;
    border-radius: 25px;
    padding: 3px;
    margin: 20px 0;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.progress-bar {
    height: 30px;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    border-radius: 25px;
    transition: width 0.5s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 14px;
}

.milestone-badge {
    display: inline-block;
    padding: 8px 15px;
    border-radius: 20px;
    margin: 5px;
    font-weight: bold;
    font-size: 14px;
    animation: badge-pop 0.5s ease;
}

@keyframes badge-pop {
    0% { transform: scale(0); }
    50% { transform: scale(1.2); }
    100% { transform: scale(1); }
}

.badge-25 { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
.badge-50 { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
.badge-75 { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }
.badge-100 { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; }

.trait-badge {
    display: inline-block;
    padding: 10px 20px;
    border-radius: 25px;
    margin: 10px 5px;
    font-weight: bold;
    font-size: 16px;
    color: white;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.trait-R { background: linear-gradient(135deg, #f39c12 0%, #e74c3c 100%); }
.trait-I { background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); }
.trait-A { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }
.trait-S { background: linear-gradient(135deg, #1abc9c 0%, #16a085 100%); }
.trait-E { background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); }
.trait-C { background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%); }
</style>
"""

# -------------------------
# QUESTIONS (Q1..Q42) - with emojis
# -------------------------
QUESTIONS = [
    (1, "Q1. I like to work on cars 🚗", 'R'),
    (2, "Q2. I like to do puzzles 🧩", 'I'),
    (3, "Q3. I am good at working independently 🧑‍💼", 'A'),
    (4, "Q4. I like to work in teams 👥", 'S'),
    (5, "Q5. I am an ambitious person, I set goals for myself 🎯", 'E'),
    (6, "Q6. I like to organize things, (files, desks/offices) 📁", 'C'),
    (7, "Q7. I like to build things 🔨", 'R'),
    (8, "Q8. I like to read about art and music 📚", 'A'),
    (9, "Q9. I like to have clear instructions to follow 📋", 'C'),
    (10, "Q10. I like to try to influence or persuade people 💬", 'E'),
    (11, "Q11. I like to do experiments 🧪", 'I'),
    (12, "Q12. I like to teach or train people 👨‍🏫", 'S'),
    (13, "Q13. I like trying to help people solve their problems 🤝", 'S'),
    (14, "Q14. I like to take care of animals 🐕", 'R'),
    (15, "Q15. I wouldn't mind working 8 hours per day in an office 🏢", 'C'),
    (16, "Q16. I like selling things 🛒", 'E'),
    (17, "Q17. I enjoy creative writing ✍️", 'A'),
    (18, "Q18. I enjoy science 🔬", 'I'),
    (19, "Q19. I am quick to take on new responsibilities 📈", 'E'),
    (20, "Q20. I am interested in healing people 💊", 'S'),
    (21, "Q21. I enjoy trying to figure out how things work ⚙️", 'I'),
    (22, "Q22. I like putting things together or assembling things 🔧", 'R'),
    (23, "Q23. I am a creative person 🎨", 'A'),
    (24, "Q24. I pay attention to details 🔍", 'C'),
    (25, "Q25. I like to do filing or typing ⌨️", 'C'),
    (26, "Q26. I like to analyze things (problems/ situations) 📊", 'I'),
    (27, "Q27. I like to play instruments or sing 🎵", 'A'),
    (28, "Q28. I enjoy learning about other cultures 🌍", 'S'),
    (29, "Q29. I would like to start my own business 💼", 'E'),
    (30, "Q30. I like to cook 🍳", 'R'),
    (31, "Q31. I like acting in plays 🎭", 'A'),
    (32, "Q32. I am a practical person 🛠️", 'R'),
    (33, "Q33. I like working with numbers or charts 📉", 'I'),
    (34, "Q34. I like to get into discussions about issues 💭", 'S'),
    (35, "Q35. I am good at keeping records of my work 📝", 'C'),
    (36, "Q36. I like to lead 👑", 'E'),
    (37, "Q37. I like working outdoors 🌳", 'R'),
    (38, "Q38. I would like to work in an office 💻", 'C'),
    (39, "Q39. I'm good at math ➕", 'I'),
    (40, "Q40. I like helping people ❤️", 'S'),
    (41, "Q41. I like to draw ✏️", 'A'),
    (42, "Q42. I like to give speeches 🎤", 'E'),
]
TRAITS = ['R', 'I', 'A', 'S', 'E', 'C']

TRAIT_NAMES = {
    'R': 'Realistic',
    'I': 'Investigative', 
    'A': 'Artistic',
    'S': 'Social',
    'E': 'Enterprising',
    'C': 'Conventional'
}

TRAIT_DESCRIPTIONS = {
    'R': '🔧 The Doer - Hands-on, practical, and mechanical',
    'I': '🔬 The Thinker - Analytical, intellectual, and research-oriented',
    'A': '🎨 The Creator - Creative, expressive, and design-oriented',
    'S': '🤝 The Helper - Helping, teaching, and service-oriented',
    'E': '📈 The Persuader - Leadership, business-focused, and persuasive',
    'C': '📊 The Organizer - Structured, detail-oriented, and data-driven'
}

# -------------------------
# COURSES (12 titles - trimmed down)
# -------------------------
COURSES = [
    "BIOLOGY",
    "DATA ANALYSIS",
    "ECONOMICS",
    "LAW",
    "CHEMISTRY",
    "HOTEL MANAGEMENT",
    "ADVERTISING",
    "CIVIL ENGINEERING",
    "INTERIOR DESIGN",
    "LANGUAGE STUDIES",
    "PSYCHOLOGY",
    "COMPUTER PROGRAMMING"
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

def make_radar_chart(scores_df, title="RIASEC Profile", for_card=False):
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
        textfont=dict(color='black', size=12 if for_card else 14),
        hovertemplate='%{theta}: %{r:.1f}%<extra></extra>'
    ))
    
    # Always use white background
    paper_bg = 'white'
    plot_bg = 'white'
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True, 
                range=[0, range_max], 
                tickformat=".0f",
                tickfont=dict(color='black')
            ),
            angularaxis=dict(
                tickfont=dict(color='black', size=12 if for_card else 14)
            )
        ),
        showlegend=False,
        title=dict(text=title, font=dict(color='black', size=16 if for_card else 20)),
        height=400 if for_card else 650,
        margin=dict(l=30, r=30, t=80, b=30),
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg
    )
    return fig

def calculate_progress():
    total_questions = len(QUESTIONS)
    answered = sum(1 for qid, _, _ in QUESTIONS if st.session_state.get(f"q_{qid}") not in ["—", None])
    
    consent_complete = (st.session_state.get('consent_purpose', False) and 
                       st.session_state.get('consent_confidentiality', False) and 
                       st.session_state.get('consent_participate', False))
    
    basic_info = bool(st.session_state.get('name_input', '').strip()) and bool(st.session_state.get('degree_input', '').strip())
    
    steps = 3
    progress = 0
    if consent_complete:
        progress += 33.3
    if basic_info:
        progress += 33.3
    progress += (answered / total_questions) * 33.4
    
    return min(100, progress), answered, total_questions

def display_progress_bar():
    progress, answered, total = calculate_progress()
    
    st.markdown(PROGRESS_CSS, unsafe_allow_html=True)
    
    progress_html = f"""
    <div class="sticky-progress">
        <div class="progress-container">
            <div class="progress-bar" style="width: {progress}%;">
                {progress:.0f}% Complete
            </div>
        </div>
        <p style="text-align: center; color: #666; margin-top: 5px;">
            Questions: {answered}/{total} answered
        </p>
    </div>
    """
    st.markdown(progress_html, unsafe_allow_html=True)

def display_milestone_badges():
    progress, _, _ = calculate_progress()
    
    badges_html = '<div style="text-align: center; margin: 20px 0;">'
    
    milestones = [
        (25, "🌟 Getting Started", "badge-25"),
        (50, "⚡ Half Way There", "badge-50"),
        (75, "🔥 Almost Done", "badge-75"),
        (100, "🎉 Survey Complete!", "badge-100")
    ]
    
    for threshold, label, css_class in milestones:
        if progress >= threshold:
            badges_html += f'<span class="milestone-badge {css_class}">{label}</span>'
    
    badges_html += '</div>'
    
    if progress >= 25:
        st.markdown(badges_html, unsafe_allow_html=True)

def get_dominant_traits(scores_df, top_n=3):
    sorted_df = scores_df.sort_values('score_percent', ascending=False)
    return sorted_df.head(top_n)

def display_trait_badges(scores_df):
    dominant = get_dominant_traits(scores_df, top_n=3)
    
    badges_html = '<div style="text-align: center; margin: 20px 0;"><h3>🏆 Your Top Traits</h3>'
    
    for idx, row in dominant.iterrows():
        trait = row['trait']
        percent = row['score_percent']
        name = TRAIT_NAMES[trait]
        desc = TRAIT_DESCRIPTIONS[trait]
        
        if percent > 0:
            badges_html += f'<div class="trait-badge trait-{trait}">{name}: {percent:.1f}%<br><small>{desc}</small></div>'
    
    badges_html += '</div>'
    st.markdown(badges_html, unsafe_allow_html=True)

def create_results_card(name, scores_df):
    width, height = 800, 1700
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try multiple font paths for better compatibility
    font_loaded = False
    try:
        # Try common font paths on different systems
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        
        for font_path in font_paths:
            try:
                title_font = ImageFont.truetype(font_path, 72)
                name_font = ImageFont.truetype(font_path, 56)
                trait_font = ImageFont.truetype(font_path, 28)
                table_font = ImageFont.truetype(font_path.replace("Bold", "Regular").replace("bd", ""), 22)
                desc_font = ImageFont.truetype(font_path.replace("Bold", "Regular").replace("bd", ""), 18)
                footer_font = ImageFont.truetype(font_path.replace("Bold", "Regular").replace("bd", ""), 16)
                font_loaded = True
                break
            except:
                continue
                
        if not font_loaded:
            raise Exception("No fonts found")
            
    except:
        # If all font paths fail, create larger default fonts by scaling
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        trait_font = ImageFont.load_default()
        table_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()
        
        # Show warning that fonts couldn't load
        print("Warning: Could not load custom fonts, using default fonts")
    
    # Draw header background with gradient effect (larger)
    draw.rectangle([0, 0, width, 220], fill='#667eea')
    
    # Draw title (larger and more prominent)
    title = "RIASEC PROFILE"
    try:
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) / 2
    except:
        # Fallback for default font
        title_width = len(title) * 40  # Estimate
        title_x = (width - title_width) / 2
    
    draw.text((title_x, 25), title, fill='white', font=title_font)
    
    # Draw name directly without icon - left aligned with good spacing
    name_x = 60
    name_y = 140
    draw.text((name_x, name_y), name, fill='white', font=name_font)
    
    # RIASEC Table with borders (adjust starting position)
    y_offset = 260
    table_title = "RIASEC Scores"
    draw.text((50, y_offset), table_title, fill='#2c3e50', font=trait_font)
    y_offset += 50
    
    # Table dimensions
    table_x = 60
    table_width = 340
    row_height = 35
    col1_width = 100
    col2_width = 240
    
    # Draw outer table border
    table_height = row_height * 7  # Header + 6 traits
    draw.rectangle([table_x, y_offset, table_x + table_width, y_offset + table_height], 
                   outline='#ccc', width=2)
    
    # Draw header row with background
    draw.rectangle([table_x, y_offset, table_x + table_width, y_offset + row_height], 
                   fill='#f0f0f0', outline='#ccc', width=1)
    draw.text((table_x + 20, y_offset + 8), "Trait", fill='#333', font=table_font)
    draw.text((table_x + col1_width + 20, y_offset + 8), "Score %", fill='#333', font=table_font)
    
    # Draw vertical line between columns
    draw.line([(table_x + col1_width, y_offset), 
               (table_x + col1_width, y_offset + table_height)], 
              fill='#ccc', width=1)
    
    y_offset += row_height
    
    # Draw table rows with borders
    for idx, row in scores_df.iterrows():
        trait = row['trait']
        percent = row['score_percent']
        
        # Draw horizontal line
        draw.line([(table_x, y_offset), (table_x + table_width, y_offset)], 
                  fill='#ccc', width=1)
        
        # Draw cell content
        draw.text((table_x + 20, y_offset + 8), trait, fill='#333', font=table_font)
        draw.text((table_x + col1_width + 20, y_offset + 8), f"{percent:.1f}%", fill='#333', font=table_font)
        
        y_offset += row_height
    
    y_offset += 20
    chart_y_position = y_offset
    
    try:
        fig = make_radar_chart(scores_df, title="", for_card=True)
        # Override colors to match the on-page chart with light blue fill and dark blue line
        fig.data[0].fillcolor = 'rgba(135, 206, 250, 0.6)'  # Light blue with transparency
        fig.data[0].line.color = '#1e3a8a'  # Dark blue
        fig.data[0].line.width = 2
        
        # Ensure white background
        fig.update_layout(
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        chart_img_bytes = fig.to_image(format="png", width=700, height=400)
        chart_img = Image.open(BytesIO(chart_img_bytes))
        chart_x = (width - 700) // 2
        img.paste(chart_img, (chart_x, chart_y_position))
        y_offset = chart_y_position + 420
    except Exception as e:
        chart_text = "RIASEC Radar Chart"
        chart_bbox = draw.textbbox((0, 0), chart_text, font=trait_font)
        chart_width = chart_bbox[2] - chart_bbox[0]
        draw.text(((width - chart_width) / 2, chart_y_position + 150), chart_text, fill='#999', font=trait_font)
        
        y_temp = chart_y_position + 200
        for idx, row in scores_df.iterrows():
            trait = row['trait']
            percent = row['score_percent']
            score_text = f"{trait}: {percent:.1f}%"
            draw.text((300, y_temp), score_text, fill='#333', font=desc_font)
            y_temp += 30
        
        y_offset = chart_y_position + 450
    
    # Add "Your Top Traits" section with 3 colored boxes matching the style
    y_offset += 40
    top_traits_title = "Your Top Traits"
    top_traits_bbox = draw.textbbox((0, 0), top_traits_title, font=trait_font)
    top_traits_width = top_traits_bbox[2] - top_traits_bbox[0]
    draw.text(((width - top_traits_width) / 2, y_offset), top_traits_title, fill='#2c3e50', font=trait_font)
    y_offset += 60
    
    sorted_scores = scores_df.sort_values('score_percent', ascending=False).head(3)
    
    # Color gradients for each trait
    trait_gradients = {
        'R': '#e67e22',  # Orange
        'I': '#3498db',  # Blue
        'A': '#e74c3c',  # Red
        'S': '#1abc9c',  # Teal/Green
        'E': '#9b59b6',  # Purple
        'C': '#34495e'   # Dark gray
    }
    
    # Define box width (centered, with margins)
    box_margin = 50
    box_width = width - (2 * box_margin)
    box_height = 70
    box_radius = 35  # Highly rounded corners
    
    for idx, row in sorted_scores.iterrows():
        trait = row['trait']
        percent = row['score_percent']
        name_full = TRAIT_NAMES[trait]
        
        # Get description without emoji and "The X -" prefix
        desc_parts = TRAIT_DESCRIPTIONS[trait].split(' - ')
        if len(desc_parts) > 1:
            description = desc_parts[1]
        else:
            description = TRAIT_DESCRIPTIONS[trait]
        
        color = trait_gradients[trait]
        
        # Draw highly rounded rectangle
        draw.rounded_rectangle([box_margin, y_offset, box_margin + box_width, y_offset + box_height], 
                              radius=box_radius, fill=color)
        
        # Draw trait title (larger font, centered vertically) - NO ICONS
        title_text = f"{name_full}: {percent:.1f}%"
        draw.text((box_margin + 25, y_offset + 10), title_text, fill='white', font=trait_font)
        
        # Draw description (smaller font, below title) - NO ICONS
        desc_text = f"The {name_full.split()[0]} - {description}"
        draw.text((box_margin + 25, y_offset + 42), desc_text, fill='white', font=desc_font)
        
        y_offset += box_height + 15  # Space between boxes
    
    footer_y = y_offset
    footer_text = [
        "This assessment was conducted by Jain University and designed to identify",
        "your primary vocational interest types among six categories:",
        "",
        "🔧 Realistic (R): Hands-on, practical, and mechanical work.",
        "🔬 Investigative (I): Analytical, intellectual, and research-oriented roles.",
        "🎨 Artistic (A): Creative, expressive, and design-oriented activities.",
        "🤝 Social (S): Helping, teaching, or service-oriented careers.",
        "📈 Enterprising (E): Persuasive, leadership, and business-focused roles.",
        "📊 Conventional (C): Structured, detail-oriented, and data-driven work.",
        "",
        "Your scores reflect your preferences, not your abilities or limitations.",
        "There are no 'right' or 'wrong' answers in this assessment."
    ]
    
    line_height = 22
    for i, line in enumerate(footer_text):
        y_pos = footer_y + (i * line_height)
        if y_pos + line_height < height - 10:
            draw.text((30, y_pos), line, fill='#666', font=footer_font)
    
    return img

def image_to_base64(img):
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Session state initialization
if 'course_checks' not in st.session_state or len(st.session_state.course_checks) != len(COURSES):
    st.session_state.course_checks = [False] * len(COURSES)

for qid, _, _ in QUESTIONS:
    key = f"q_{qid}"
    if key not in st.session_state:
        st.session_state[key] = "—"

if 'consent_purpose' not in st.session_state:
    st.session_state.consent_purpose = False
if 'consent_confidentiality' not in st.session_state:
    st.session_state.consent_confidentiality = False
if 'consent_participate' not in st.session_state:
    st.session_state.consent_participate = False

if 'survey_submitted' not in st.session_state:
    st.session_state.survey_submitted = False
if 'final_scores_df' not in st.session_state:
    st.session_state.final_scores_df = None
if 'final_name' not in st.session_state:
    st.session_state.final_name = ""

# Main UI
st.title("🎯 RIASEC Career Interest Survey")

gc, spreadsheet_id = get_gspread_client_from_secrets()
if not gc:
    st.error("Google Sheets not configured or secrets missing. Please fix st.secrets.")
    st.stop()

# Only show milestone badges, not progress bar
if not st.session_state.survey_submitted:
    display_milestone_badges()

# CONSENT FORM SECTION
st.header("📋 Informed Consent")

st.subheader("Title of the Study: Assessing Student Vocational Interests Using The RIASEC Framework")
st.markdown("**Principal Investigator/Administrator:** Sriharsha Ganjam - sriharsha.g@jainuniversity.ac.in , Shambhavi Priya - 24msrps055@jainuniversity.ac.in")

with st.expander("📖 Purpose Statement", expanded=False):
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
    "✅ I understand the purpose of this study and survey",
    key="consent_purpose_check",
    value=st.session_state.consent_purpose
)
st.session_state.consent_purpose = consent_purpose

with st.expander("🔒 Confidentiality Statement", expanded=False):
    st.markdown("""
    All responses will be treated with strict confidentiality. Data will be stored securely and analyzed
    only in aggregated form. No personally identifiable information will be disclosed in reports or
    publications arising from this study.
    """)

consent_confidentiality = st.checkbox(
    "✅ I understand the confidential implications of this survey",
    key="consent_confidentiality_check",
    value=st.session_state.consent_confidentiality
)
st.session_state.consent_confidentiality = consent_confidentiality

with st.expander("📝 Consent Statement", expanded=False):
    st.markdown("""
    By proceeding with this survey, you acknowledge that you have read and understood the above
    information and voluntarily consent to participate in this RIASEC-based study.
    """)

consent_participate = st.checkbox(
    "✅ I agree to participate voluntarily in this survey",
    key="consent_participate_check",
    value=st.session_state.consent_participate
)
st.session_state.consent_participate = consent_participate

all_consents_given = consent_purpose and consent_confidentiality and consent_participate

if not all_consents_given:
    st.warning("⚠️ Please check all three consent boxes above to proceed with the survey.")
    st.stop()

st.success("✅ Consent received. You may now proceed with the survey.")
st.markdown("---")

# SURVEY SECTION
st.header("👤 Your Information")

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Student name *", key="name_input", placeholder="Enter your full name")
with col2:
    degree = st.text_input("Current Enrolled Degree *", key="degree_input", placeholder="e.g., B.Sc Computer Science")

email = st.text_input("Email (optional)", key="email_input", placeholder="your.email@example.com")

st.markdown("---")
st.header("📝 Survey Questions")
st.markdown("**Note:** All questions are mandatory. Please choose either a 'YES' or a 'NO' for the below questions")

answers = []
for qid, text, trait in QUESTIONS:
    choice = st.radio(f"{text}", options=["—", "Yes", "No"], index=0, key=f"q_{qid}", horizontal=True)
    val = 1 if choice == "Yes" else 0 if choice == "No" else None
    answers.append((qid, trait, val))

st.markdown("---")
st.header("💡 Course Interest Selection")
st.markdown("### THOUGHT EXPERIMENT ON CHOICE")
st.markdown("**If you have a chance to pick 4 courses to study, purely based on your interest & passion what courses would you like to study?**")
st.markdown("1. You must select between 2 to 4 courses.\n2. Please be candid in your response.\n3. The selection has to be only based on your interest and passion, so it's ok to choose a course even if you have no prior experience in that course.")
st.markdown("---")

cols = st.columns(3)
for col_idx, col in enumerate(cols):
    with col:
        start = col_idx * 4
        end = min(start + 4, len(COURSES))
        for i in range(start, end):
            checked = st.checkbox(COURSES[i], key=f"course_{i}", value=st.session_state.course_checks[i])
            st.session_state.course_checks[i] = checked

selected_count = sum(1 for v in st.session_state.course_checks if v)
st.markdown(f"**Selected:** {selected_count} / 4")
if selected_count > 4:
    over = selected_count - 4
    st.error(f"You selected {selected_count} courses — the maximum allowed is 4. Please uncheck {over} course(s).")

missing_qs = [f"Q{qid}" for qid, trait, val in answers if val is None]
all_questions_answered = (len(missing_qs) == 0)
basic_info_ok = bool(name.strip()) and bool(degree.strip())
submit_enabled = basic_info_ok and all_questions_answered and (0 <= selected_count <= 7)

st.markdown("---")

if not basic_info_ok:
    st.info("ℹ️ Please enter your name and your current enrolled degree.")
if missing_qs:
    st.info(f"ℹ️ Please answer all questions. Missing: {', '.join(missing_qs)}")
if selected_count == 0:
    st.info("ℹ️ Please select up to a max of 4 courses from the above list.")
if selected_count > 4:
    st.info("ℹ️ Reduce your selected courses to at most 4 to enable Submit.")

# Only show submit button if survey not yet submitted
if not st.session_state.survey_submitted:
    if st.button("🚀 Submit Survey", disabled=not submit_enabled, type="primary", use_container_width=True):
        if not basic_info_ok:
            st.error("Please fill Name and Degree.")
        elif missing_qs:
            st.error("Please answer all questions before submitting.")
        elif selected_count < 2:
            st.error("Please select at least 2 courses.")
        elif selected_count > 4:
            st.error(f"Too many selections ({selected_count}) — please select at most 4.")
        else:
            with st.spinner("✨ Processing your results..."):
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
                        st.session_state.survey_submitted = True
                        st.session_state.final_scores_df = scores_df
                        st.session_state.final_name = name.strip()
                        st.rerun()

# RESULTS SECTION
if st.session_state.survey_submitted and st.session_state.final_scores_df is not None:
    st.balloons()
    
    st.success("✅ Submission saved successfully!")
    
    st.markdown("---")
    st.header("🎉 Congratulations! Survey Complete!")
    
    st.markdown("""
    <div style="border: 2px solid #cccccc; padding: 20px; border-radius: 10px; margin: 20px 0; background-color: transparent;">
    <h3 style="color: #2c3e50; margin-top: 0;">Thank you for participating in the RIASEC Vocational Interest Survey! 🌟</h3>
    
    This assessment is designed to identify your primary vocational interest types among six categories:<br><br>
    
    <b>🔧 Realistic (R):</b> Hands-on, practical, and mechanical work.<br>
    <b>🔬 Investigative (I):</b> Analytical, intellectual, and research-oriented roles.<br>
    <b>🎨 Artistic (A):</b> Creative, expressive, and design-oriented activities.<br>
    <b>🤝 Social (S):</b> Helping, teaching, or service-oriented careers.<br>
    <b>📈 Enterprising (E):</b> Persuasive, leadership, and business-focused roles.<br>
    <b>📊 Conventional (C):</b> Structured, detail-oriented, and data-driven work.<br><br>
    
    <i>Your scores reflect your preferences, not your abilities or limitations. There are no "right" or "wrong" answers in this assessment. The results will assist in identifying environments and tasks where you are most likely to find satisfaction and success.</i>
    </div>
    """, unsafe_allow_html=True)
    
    # Create downloadable results card from entire results section
    results_card = create_results_card(st.session_state.final_name, st.session_state.final_scores_df)
    
    # Provide download button at top
    st.markdown("### 📥 Download Your Results")
    img_buffer = BytesIO()
    results_card.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()
    
    st.download_button(
        label="⬇️ Download Complete Results Card",
        data=img_bytes,
        file_name=f"RIASEC_Results_{st.session_state.final_name.replace(' ', '_')}.png",
        mime="image/png",
        type="primary",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # Display results on screen
    display_trait_badges(st.session_state.final_scores_df)
    
    st.markdown("---")
    st.subheader("📊 Your RIASEC Profile")
    
    display_df = st.session_state.final_scores_df.set_index("trait")[["yes_count", "n_items", "prop", "score_percent"]].rename(
        columns={"prop":"proportion","score_percent":"standardized_percent"}
    )
    st.table(display_df)
    
    st.plotly_chart(make_radar_chart(st.session_state.final_scores_df, for_card=False), use_container_width=True)
    
    st.markdown("---")
    st.info("💡 **Thankyou for your time!**")
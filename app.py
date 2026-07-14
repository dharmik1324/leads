import sys
import streamlit as st

# Check for missing imports
missing_packages = []

try:
    import playwright
except ImportError:
    missing_packages.append("playwright")

try:
    import pandas as pd
except ImportError:
    missing_packages.append("pandas")

try:
    import duckduckgo_search
except ImportError:
    missing_packages.append("duckduckgo-search (ddgs)")

try:
    import openpyxl
except ImportError:
    missing_packages.append("openpyxl")

if missing_packages:
    st.set_page_config(page_title="LeadScout AI - Error", page_icon="⚠️", layout="wide")
    st.error("### ⚠️ Missing Required Libraries")
    st.write(f"The following required python packages are missing: **{', '.join(missing_packages)}**")
    st.info("This usually happens if Streamlit was launched outside the project's virtual environment.")
    st.markdown("To resolve this, please stop the current server (Ctrl+C) and run these commands in your terminal:")
    st.code("source .venv/bin/activate && pip install -r requirements.txt")
    st.stop()

import io
import time
from scraper import scrape_maps_leads

# Session state initialization
if "leads_data" not in st.session_state:
    st.session_state.leads_data = None
if "run_logs" not in st.session_state:
    st.session_state.run_logs = []
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Config page
st.set_page_config(page_title="LeadScout AI - Maps Lead Generator", page_icon="🌐", layout="wide")

# Helper to build log HTML with dynamic styling based on log types
def get_log_html(logs):
    if not logs:
        return """
        <div class="terminal-body">
            <div class="terminal-line info">&gt; System: Console ready.</div>
            <div class="terminal-line info">&gt; Setup search parameters on the left and click "Start Scraping Agent".</div>
        </div>
        """
    
    html = '<div class="terminal-body" id="terminal-console">'
    for log in logs:
        log_lower = log.lower()
        log_class = "info"
        if "error" in log_lower or "failed" in log_lower or "fatal" in log_lower:
            log_class = "error"
        elif "success" in log_lower or "completed" in log_lower or "added" in log_lower or "found" in log_lower or "scraped" in log_lower:
            log_class = "success"
        elif "warning" in log_lower or "skipping" in log_lower or "already" in log_lower:
            log_class = "warning"
            
        html += f'<div class="terminal-line {log_class}">&gt; {log}</div>'
    html += '</div>'
    # Auto-scroll script to ensure new console entries are displayed
    html += """
    <script>
        var el = document.getElementById("terminal-console");
        if (el) { el.scrollTop = el.scrollHeight; }
    </script>
    """
    return html

# Custom premium CSS styling (Dynamic variables native to Streamlit theme, Outfit font)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

/* Apply font to elements */
html, body, [class*="css"], .stMarkdown {
    font-family: 'Outfit', sans-serif !important;
}

/* Background styling overrides */
.stApp {
    background: var(--background-color) !important;
    color: var(--text-color) !important;
}

/* Make side bar elements match */
[data-testid="stSidebar"] {
    background-color: var(--secondary-background-color) !important;
    border-right: 1px solid rgba(139, 92, 246, 0.15) !important;
}

/* Headers style with light classic font-weight */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Outfit', sans-serif !important;
    color: var(--text-color) !important;
    font-weight: 500 !important;
}

/* Main title styling */
.main-title {
    font-weight: 600;
    font-size: 2.8rem;
    background: linear-gradient(90deg, #a855f7 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0px 4px 15px rgba(168, 85, 247, 0.15);
}

.sub-title {
    font-size: 1.05rem;
    color: var(--text-color) !important;
    opacity: 0.7;
    margin-bottom: 30px;
    font-weight: 300;
}

/* Cards layout for metrics */
.card {
    background: var(--secondary-background-color);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 16px;
    padding: 22px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
    margin-bottom: 20px;
    border-top: 3px solid var(--primary-color, #8b5cf6);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.card:hover {
    transform: translateY(-5px);
    border-color: var(--primary-color, #8b5cf6);
    box-shadow: 0 12px 40px rgba(139, 92, 246, 0.15);
}
.card-header-row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
.card-icon {
    color: var(--primary-color, #8b5cf6);
    filter: drop-shadow(0 0 6px rgba(139, 92, 246, 0.3));
}
.card-number {
    font-size: 2.6rem;
    font-weight: 700;
    color: var(--text-color);
    background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.card-label {
    font-size: 0.88rem;
    color: var(--text-color) !important;
    opacity: 0.8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
}

/* Custom styled inputs container card */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--secondary-background-color) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08) !important;
}

/* Inputs styling */
.stTextInput input, .stSelectbox [data-baseweb="select"] {
    background-color: var(--background-color) !important;
    color: var(--text-color) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 10px !important;
}
.stTextInput input:focus, .stSelectbox [data-baseweb="select"]:focus-within {
    border-color: var(--primary-color, #8b5cf6) !important;
    box-shadow: 0 0 8px rgba(139, 92, 246, 0.4) !important;
}

/* Slider theme adjustments */
.stSlider [data-testid="stThumb"] {
    background-color: var(--primary-color, #8b5cf6) !important;
    border: 2px solid #ffffff !important;
}
.stSlider [data-testid="stTrack"] {
    background: linear-gradient(90deg, #8b5cf6 0%, #3b82f6 100%) !important;
}

/* Primary Action Buttons */
.stButton button {
    background: linear-gradient(90deg, #8b5cf6 0%, #3b82f6 100%) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 12px 24px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4) !important;
    width: 100%;
    font-size: 1.05rem !important;
    letter-spacing: 0.5px !important;
    margin-top: 10px !important;
}
.stButton button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(139, 92, 246, 0.6) !important;
    background: linear-gradient(90deg, #9333ea 0%, #2563eb 100%) !important;
}
.stButton button:active {
    transform: translateY(0px) !important;
}

/* Terminal Console Styling */
.terminal-header {
    background-color: var(--secondary-background-color);
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 10px 18px;
    font-size: 0.85rem;
    color: var(--text-color);
    opacity: 0.9;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-bottom: none;
    display: flex;
    align-items: center;
}
.terminal-dot {
    height: 12px;
    width: 12px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
}
.red { background-color: #ef4444; box-shadow: 0 0 8px rgba(239, 68, 68, 0.6); }
.yellow { background-color: #eab308; box-shadow: 0 0 8px rgba(234, 179, 8, 0.6); }
.green { background-color: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.6); }
.terminal-title {
    margin-left: 8px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

.terminal-body {
    background-color: #090514; /* Keep terminal body dark slate to maintain classic shell feel */
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    padding: 18px;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.88rem;
    height: 350px;
    overflow-y: auto;
    margin-bottom: 25px;
    box-shadow: inset 0 0 24px rgba(139, 92, 246, 0.1);
}
.terminal-line {
    font-family: 'JetBrains Mono', monospace !important;
    margin-bottom: 6px;
    line-height: 1.5;
    border-left: 2px solid transparent;
    padding-left: 8px;
}
.terminal-line.info {
    color: #38bdf8 !important;
}
.terminal-line.success {
    color: #4ade80 !important;
    border-left-color: #22c55e !important;
}
.terminal-line.warning {
    color: #fbbf24 !important;
    border-left-color: #d97706 !important;
}
.terminal-line.error {
    color: #f87171 !important;
    border-left-color: #dc2626 !important;
    background-color: rgba(220, 38, 38, 0.05);
}

/* Custom premium download button styles */
div[data-testid="stDownloadButton"] button {
    background: linear-gradient(90deg, #10b981 0%, #059669 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2) !important;
    width: 100%;
}
div[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4) !important;
    background: linear-gradient(90deg, #34d399 0%, #059669 100%) !important;
}

/* Styling native streamlit tables */
[data-testid="stTable"] {
    background-color: var(--secondary-background-color) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 12px !important;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# Process and save logo if not already processed (runs on the host machine where Streamlit is launched)
logo_path = "logo_transparent.png"
raw_logo_path = "/Users/dharmik/.gemini/antigravity-ide/brain/772258eb-c840-49d7-9480-fd1530725167/media__1782814223726.png"

import os
if not os.path.exists(logo_path) and os.path.exists(raw_logo_path):
    try:
        from PIL import Image
        img = Image.open(raw_logo_path)
        img = img.convert("RGBA")
        datas = img.getdata()
        
        newData = []
        for item in datas:
            # If the pixel is white or near white, make it transparent
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                newData.append((255, 255, 255, 0))
            else:
                # Shift dark text slightly to be readable on dark backgrounds
                if item[0] < 50 and item[1] < 50 and item[2] < 50:
                    newData.append((148, 163, 184, item[3]))
                else:
                    newData.append(item)
                    
        img.putdata(newData)
        img.save(logo_path, "PNG")
    except Exception as e:
        pass

# Render header logo
if os.path.exists(logo_path):
    st.image(logo_path, width=280)
else:
    # Fallback to text title
    st.markdown('<div class="main-title">Firevy Leads</div>', unsafe_allow_html=True)

st.markdown('<div class="sub-title">Google Maps Lead Generation Agent for Website-less Businesses</div>', unsafe_allow_html=True)

# Main dashboard layout
col_setup, col_console = st.columns([5, 7])

with col_setup:
    st.markdown("### Search Setup")
    with st.container(border=True):
        category = st.selectbox(
            "Business Category", 
            ["Plumbers", "Handyman", "Roofers", "Electricians", "Locksmiths", "Painters", "Landscapers", "Junk Removal", "Custom Category"],
            help="Select a common business type that typically lacks websites, or choose Custom"
        )
        
        if category == "Custom Category":
            custom_category = st.text_input("Enter Custom Category", "Hardware stores", help="Type any business type")
            selected_category = custom_category
        else:
            selected_category = category

        location = st.text_input("Location (City, State / ZIP)", "Dallas, TX", help="E.g. Dallas, TX or 90210")
        limit_input = st.number_input("Max Leads to Collect", min_value=1, value=20, step=1, help="Target number of website-less business leads to collect")
        
        query_input = f"{selected_category} in {location}"
        
        # Primary Action Button
        run_btn = st.button("🚀 Start Scraping Agent")

# Sidebar Google Sheets Sync config
with st.sidebar:
    st.markdown("### 📊 Google Sheets Sync")
    with st.container(border=True):
        gsheet_enabled = st.checkbox("Export to Google Sheets", value=False, help="Automatically sync results to a Google Sheet")
        if gsheet_enabled:
            st.markdown("---")
            gsheet_name = st.text_input("Spreadsheet Name", "LeadScout Scraped Leads", help="Google Spreadsheet Name")
            gsheet_sheet = st.text_input("Worksheet Name", "Sheet1", help="Name of the worksheet tab")
            gsheet_creds = st.text_input("Credentials File Path", "credentials.json", help="Path to your credentials JSON file")

with col_console:
    st.markdown("### Agent Operations Console")
    
    # Terminal Header
    st.markdown("""
    <div class="terminal-header">
        <span class="terminal-dot red"></span>
        <span class="terminal-dot yellow"></span>
        <span class="terminal-dot green"></span>
        <span class="terminal-title">LeadScout Agent Terminal Console</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Terminal Body Area
    log_area = st.empty()

# Scraper Execution
if run_btn:
    st.session_state.run_logs = []
    st.session_state.leads_data = None
    st.session_state.is_running = True
    
    def log_to_web(message):
        st.session_state.run_logs.append(message)
        # Render live log list to web console
        log_area.markdown(get_log_html(st.session_state.run_logs), unsafe_allow_html=True)
        
    start_time = time.time()
    log_to_web("Initializing LeadScout scraper agent...")
    log_to_web(f"Query parameters: Query='{query_input}', Max Search Limit={limit_input}")
    
    try:
        # Run scraper core
        leads = scrape_maps_leads(query_input, max_results=limit_input, log_callback=log_to_web)
        
        duration = round(time.time() - start_time, 1)
        log_to_web(f"Scrape completed successfully in {duration} seconds!")
        log_to_web(f"Found {len(leads)} website-less business leads matching criteria.")
        
        if leads:
            st.session_state.leads_data = pd.DataFrame(leads)
            # Sync with Google Sheets if toggled
            if gsheet_enabled:
                from google_sheets import upload_leads_to_google_sheet
                upload_leads_to_google_sheet(
                    df=st.session_state.leads_data,
                    spreadsheet_name=gsheet_name,
                    credentials_path=gsheet_creds,
                    sheet_name=gsheet_sheet,
                    log_callback=log_to_web
                )
        else:
            st.session_state.leads_data = pd.DataFrame()
            
    except Exception as e:
        log_to_web(f"FATAL ERROR: Scraper failed - {e}")
        st.session_state.leads_data = pd.DataFrame()
        
    # Scrape complete
    st.session_state.is_running = False

# Render console history if not actively executing (maintains state across button presses / downloads)
if not st.session_state.is_running:
    log_area.markdown(get_log_html(st.session_state.run_logs), unsafe_allow_html=True)

# Show results if data exists
if st.session_state.leads_data is not None:
    df = st.session_state.leads_data
    
    # Add whitespace spacer
    st.markdown("<br>", unsafe_allow_html=True)
    
    if df.empty:
        st.warning("⚠️ Scraping completed but no website-less leads were found. Try modifying your search term.")
    else:
        st.markdown("### 📊 Scraped Leads Report")
        
        # Display Stats Metrics Cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="card">
                <div class="card-header-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="card-icon"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    <span class="card-label">Leads Extracted</span>
                </div>
                <div class="card-number">{len(df)}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            phone_pct = round((df['Phone'] != 'Not listed').sum() / len(df) * 100, 1) if len(df) > 0 else 0
            st.markdown(f"""
            <div class="card">
                <div class="card-header-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="card-icon"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                    <span class="card-label">Phone Coverage</span>
                </div>
                <div class="card-number">{phone_pct}%</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            email_pct = round((df['Email'] != 'Not found').sum() / len(df) * 100, 1) if len(df) > 0 else 0
            st.markdown(f"""
            <div class="card">
                <div class="card-header-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="card-icon"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                    <span class="card-label">Email Coverage</span>
                </div>
                <div class="card-number">{email_pct}%</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Display Interactive Data Table (using new non-deprecated width standard)
        st.dataframe(df, width="stretch")
        
        # Export options (CSV / Excel)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Leads')
        excel_data = excel_buffer.getvalue()
        
        col_dl1, col_dl2 = st.columns([2, 2])
        with col_dl1:
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"maps_leads_{query_input.replace(' ', '_').lower()}.csv",
                mime="text/csv"
            )
        with col_dl2:
            st.download_button(
                label="📥 Download Excel",
                data=excel_data,
                file_name=f"maps_leads_{query_input.replace(' ', '_').lower()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

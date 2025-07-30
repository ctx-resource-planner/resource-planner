import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO

CSV_FILE = "ts.csv"

st.set_page_config(layout="wide")

INTERNAL_PROJECTS = [
    "Internal", "Training", "Meeting", "CTX Internal", "CTX Training", "CTX Meeting",
    "Internal/Meeting/Training", "CTX Internal/Meeting/Training"
]
TIMEOFF_KEYWORDS = ["holiday", "vacation", "leave", "sick"]

@st.cache_data
def load_and_prepare():
    df = pd.read_csv(CSV_FILE)
    df['local_date'] = pd.to_datetime(df['local_date'], errors='coerce')
    df['MonthNum'] = df['local_date'].dt.month
    df['Month'] = df['MonthNum'].apply(lambda x: calendar.month_abbr[int(x)] if not pd.isnull(x) else '')
    df['Employee'] = (df['fname'].fillna('') + ' ' + df['lname'].fillna('')).str.strip()
    def get_proj(row):
        jc1 = str(row['jobcode_1']).lower() if not pd.isnull(row['jobcode_1']) else ''
        jc2 = str(row['jobcode_2']).strip() if not pd.isnull(row['jobcode_2']) else ''
        if jc2:
            if any(x.lower() in jc2.lower() for x in INTERNAL_PROJECTS):
                return "CTX Internal/Meeting/Training"
            return jc2
        if any(x in jc1 for x in TIMEOFF_KEYWORDS):
            return "Time Off / Holiday"
        if any(x.lower() in jc1 for x in [p.lower() for p in INTERNAL_PROJECTS]):
            return "CTX Internal/Meeting/Training"
        return "Other"
    df['Project'] = df.apply(get_proj, axis=1)
    df['billable_flag'] = df['billable'].fillna('').str.lower() == 'yes'
    df['Billable_H'] = np.where(df['billable_flag'], df['hours'], 0.0)
    df['NonBillable_H'] = np.where(~df['billable_flag'], df['hours'], 0.0)
    df = df[df['Employee'] != '']
    return df

df = load_and_prepare()

months = [calendar.month_abbr[m] for m in range(1,13)]

# --- REPORT TITLE AT THE VERY TOP ---
st.markdown(
    '<div style="background-color:#074F69;padding:7px 0 7px 0;margin-bottom:18px;text-align:center;">'
    '<span style="color:white;font-weight:bold;font-size:24px;">Resource Utilization Dashboard (Streamlit)</span>'
    '</div>',
    unsafe_allow_html=True
)

# --- FILTERS (Immediately Below Title) ---
unique_employees = sorted([e for e in df['Employee'].dropna().unique() if str(e).strip()])
unique_projects = sorted([p for p in df['Project'].dropna().unique() if str(p).strip()])
month_choices = [""] + months

col1, col2, col3 = st.columns([2,2,2])
with col1:
    emp_search = st.selectbox("Employee filter", [""] + unique_employees)
with col2:
    proj_search = st.selectbox("Project filter", [""] + unique_projects)
with col3:
    month_search = st.selectbox("Month filter", month_choices)

# Aggregate per employee/month/project
agg = df.groupby(['Employee','Project','Month']).agg(
    BillableH=('Billable_H','sum'),
    NonBillableH=('NonBillable_H','sum')
).reset_index()
agg['TotalH'] = agg['BillableH'] + agg['NonBillableH']
agg['BillableP'] = np.where(agg['TotalH']>0, (agg['BillableH']/agg['TotalH']*100), 0.0)
agg['NonBillableP'] = np.where(agg['TotalH']>0, (agg['NonBillableH']/agg['TotalH']*100), 0.0)

def get_group_rows(emp, group):
    rows = []
    # Internal/Training/Meeting
    internal = group[group['Project'] == "CTX Internal/Meeting/Training"]
    if not internal.empty:
        rows.append(("CTX Internal/Meeting/Training", internal))
    # Time Off/Holiday
    timeoff = group[group['Project'] == "Time Off / Holiday"]
    if not timeoff.empty:
        rows.append(("Time Off / Holiday", timeoff))
    # Billable projects (exclude internal/timeoff/other)
    billable = group[
        (~group['Project'].isin(["CTX Internal/Meeting/Training","Time Off / Holiday","Other"])) &
        (group['BillableH'] > 0)
    ]
    for proj in sorted(billable['Project'].unique()):
        rows.append((proj, billable[billable['Project'] == proj]))
    # TOTAL row if >1 billable project
    if len(billable['Project'].unique()) > 1:
        total = billable.groupby('Month').agg(
            BillableH=('BillableH','sum'),
            NonBillableH=('NonBillableH','sum')
        ).reset_index()
        total['TotalH'] = total['BillableH'] + total['NonBillableH']
        total['BillableP'] = np.where(total['TotalH']>0, (total['BillableH']/total['TotalH']*100), 0.0)
        total['NonBillableP'] = np.where(total['TotalH']>0, (total['NonBillableH']/total['TotalH']*100), 0.0)
        total['Project'] = "TOTAL"
        rows.append(("TOTAL", total))
    return rows

# Build the wide table
all_rows = []
for emp, emp_group in agg.groupby('Employee'):
    group_rows = get_group_rows(emp, emp_group)
    for proj, proj_group in group_rows:
        row = {"Employee": emp, "Project": proj}
        proj_months = {m: proj_group[proj_group['Month'] == m] for m in months}
        for m in months:
            g = proj_months[m]
            if not g.empty:
                bh = g['BillableH'].sum()
                bph = g['BillableP'].mean()
                nbh = g['NonBillableH'].sum()
                nbph = g['NonBillableP'].mean()
                row[f"{m} Billable H"] = f"{bh:.1f}"
                row[f"{m} Billable H(%)"] = f"{bph:.1f}"
                row[f"{m} Non-Billable H"] = f"{nbh:.1f}"
                row[f"{m} Non-Billable H(%)"] = f"{nbph:.1f}"
            else:
                row[f"{m} Billable H"] = ""
                row[f"{m} Billable H(%)"] = ""
                row[f"{m} Non-Billable H"] = ""
                row[f"{m} Non-Billable H(%)"] = ""
        all_rows.append(row)
    # Blank line after each employee
    all_rows.append({})

final = pd.DataFrame(all_rows)

def is_blank_row(row):
    return all(str(v).strip() == "" for v in row) or all(str(v).lower() == "nan" for v in row)

final = final[~final.apply(is_blank_row, axis=1)].reset_index(drop=True)

# Add SNo. column, skipping blank/separator rows
final.insert(0, "Sno.", "")
sno = 1
for idx, row in final.iterrows():
    if str(row["Employee"]).strip() and str(row["Project"]).strip():
        final.at[idx, "Sno."] = sno
        sno += 1
    else:
        final.at[idx, "Sno."] = ""

# --- Filtering on the wide table ---
view = final.copy()
if emp_search:
    view = view[view["Employee"] == emp_search]
if proj_search:
    view = view[view["Project"] == proj_search]
if month_search:
    month_cols = [c for c in view.columns if c.startswith(month_search)]
    base_cols = ["Sno.", "Employee", "Project"]
    view = view[base_cols + month_cols]

# --- Display/styling ---
def style_report(row):
    if row.get('Project') == 'TOTAL':
        return ['font-weight: bold;'] * len(row)
    return [''] * len(row)

st.markdown("""
    <style>
    .custom-table thead tr th {
        background-color: #074F69 !important;
        color: white !important;
        font-weight: bold !important;
        text-align: center !important;
        font-size: 11px !important;
        white-space: nowrap !important;
        padding: 3px 6px !important;
    }
    .custom-table thead tr th:first-child {
        background-color: #F9B572 !important;
        color: #222 !important;
        font-weight: bold !important;
        font-size: 11px !important;
        white-space: nowrap !important;
        padding: 3px 6px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="background-color:#074F69;padding:7px 0 7px 0;margin-bottom:5px;text-align:center;">'
    '<span style="color:white;font-weight:bold;font-size:20px;">Team Utilization Executive Matrix — Pivoted Format</span>'
    '</div>',
    unsafe_allow_html=True
)

if not view.empty:
    styled = view.style.apply(style_report, axis=1)
    try:
        html = styled.hide(axis="index").to_html(classes="custom-table", escape=False)
    except Exception:
        html = styled.to_html(classes="custom-table", index=False, escape=False)
        html = html.replace('<th></th>', '')
    st.markdown(html, unsafe_allow_html=True)
else:
    st.info("No data to display.")

def to_excel(df):
    out = BytesIO()
    df.to_excel(out, index=False)
    return out.getvalue()

st.download_button("Download as Excel", to_excel(final), file_name="team_utilization_table_pivoted.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
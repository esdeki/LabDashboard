# -*- coding: utf-8 -*-
"""
داشبورد آزمایشگاه دارویی — نسخهٔ کامل
- سایدبار ثابت (جزئی از layout، غیرشناور، بدون درگ و بدون دکمهٔ جمع‌شونده)
- تشخیص خودکار ردیف هدر + تطبیق هوشمند نام ستون‌ها در شیت «محصول»
- تمام تاریخ‌ها میلادی
- تم تاریک، راست‌چین، رسپانسیو
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
import zipfile

import pandas as pd
import streamlit as st

# =========================================================
# ۱. تنظیمات صفحه
# =========================================================
st.set_page_config(
    page_title="داشبورد آزمایشگاه دارویی",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

SHEET_NAME = "محصول"

STAGE_COLUMNS = [
    "تاریخ شروع آزمایشات شیمیایی",
    "تاریخ اتمام آزمایشات شیمیایی",
    "تاریخ اتمام کنترل محاسبات",
    "تاریخ اتمام بسته بندی",
    "تاریخ صدور برگ سبز",
    "تاریخ تحویل پرونده به رگولاتوری",
]
IDENTITY_COLUMNS = ["نام محصول", "شماره بچ"]
DATE_COLUMNS = ["تاریخ تحویل"] + STAGE_COLUMNS
ALL_COLUMNS = IDENTITY_COLUMNS + DATE_COLUMNS

REGULATORY_DEADLINE_DAYS = 4
DEFAULT_STAGNANT_DAYS = 15

COLUMN_ALIASES = {
    "نام محصول": ["نام محصول", "نام فرآورده", "نام فراورده", "محصول", "فرآورده",
                  "شرح کالا", "product", "product name"],
    "شماره بچ": ["شماره بچ", "شماره بچ محصول", "شماره سری ساخت", "سری ساخت", "بچ",
                 "batch", "batch no", "batch number", "lot", "lot no"],
    "تاریخ تحویل": ["تاریخ تحویل", "تاریخ تحویل نمونه", "تاریخ ورود نمونه", "تاریخ ورود",
                    "تاریخ تحویل به آزمایشگاه", "تاریخ تحویل نمونه به آزمایشگاه",
                    "تاریخ دریافت نمونه", "تاریخ دریافت"],
    "تاریخ شروع آزمایشات شیمیایی": ["تاریخ شروع آزمایشات شیمیایی", "تاریخ شروع آزمایش شیمیایی",
                                    "تاریخ شروع آزمون های شیمیایی", "تاریخ شروع آزمایش های شیمیایی",
                                    "شروع آزمایشات شیمیایی", "شروع آزمایش شیمیایی"],
    "تاریخ اتمام آزمایشات شیمیایی": ["تاریخ اتمام آزمایشات شیمیایی", "تاریخ پایان آزمایشات شیمیایی",
                                     "تاریخ اتمام آزمایش شیمیایی", "تاریخ پایان آزمون های شیمیایی",
                                     "اتمام آزمایشات شیمیایی", "پایان آزمایش شیمیایی"],
    "تاریخ اتمام کنترل محاسبات": ["تاریخ اتمام کنترل محاسبات", "تاریخ پایان کنترل محاسبات",
                                  "تاریخ کنترل محاسبات", "اتمام کنترل محاسبات", "کنترل محاسبات"],
    "تاریخ اتمام بسته بندی": ["تاریخ اتمام بسته بندی", "تاریخ پایان بسته بندی",
                              "تاریخ اتمام کنترل بسته بندی", "اتمام بسته بندی", "کنترل بسته بندی"],
    "تاریخ صدور برگ سبز": ["تاریخ صدور برگ سبز", "تاریخ برگ سبز", "صدور برگ سبز",
                           "تاریخ صدور گواهی", "برگ سبز"],
    "تاریخ تحویل پرونده به رگولاتوری": ["تاریخ تحویل پرونده به رگولاتوری",
                                        "تاریخ ارسال پرونده به رگولاتوری",
                                        "تاریخ تحویل به رگولاتوری", "تاریخ خروج پرونده",
                                        "تحویل به رگولاتوری", "ارسال به رگولاتوری"],
}

PENDING_MARKERS = {
    "not started", "notstarted", "analyzing", "analysing", "checking", "started", "pending",
    "در حال", "شروع نشده", "اغاز نشده", "ثبت نشده", "نامعتبر", "ندارد", "خالی",
    "none", "nan", "nat", "null", "*", "-", "--", "؟", "?", "—", " "
}

STAGE_LABELS = {
    "شروع نشده": "شروع نشده",
    "تاریخ شروع آزمایشات شیمیایی": "در حال آزمایش شیمیایی",
    "تاریخ اتمام آزمایشات شیمیایی": "اتمام آزمایش شیمیایی",
    "تاریخ اتمام کنترل محاسبات": "اتمام کنترل محاسبات",
    "تاریخ اتمام بسته بندی": "اتمام بسته‌بندی",
    "تاریخ صدور برگ سبز": "صدور برگ سبز",
    "تاریخ تحویل پرونده به رگولاتوری": "تحویل به رگولاتوری",
}

# =========================================================
# ۲. استایل
# =========================================================
st.markdown(
    """
    <style>
    @font-face{font-family:"Vazirmatn";src:local("Vazirmatn"),local("Vazirmatn-Regular"),local("Vazir");font-display:swap;}
    @font-face{font-family:"Nazanin";src:local("B Nazanin"),local("BNazanin"),local("Nazanin");font-display:swap;}
    @font-face{font-family:"Mitra";src:local("B Mitra"),local("BMitra"),local("Mitra");font-display:swap;}
    @font-face{font-family:"Zar";src:local("B Zar"),local("BZar"),local("Zar");font-display:swap;}

    :root{
        --bg-app:#0E1117; --bg-panel:#141A23; --bg-card:#1B212B; --bg-input:#10151D;
        --border-soft:#2E3542; --border-strong:#3D4655;
        --text-main:#F1F5F9; --text-muted:#A3ADBF;
        --accent:#3DDC97; --accent-warn:#F5A623; --accent-danger:#F16063;
        --sb-w:320px;
        --app-font:"Vazirmatn","Vazir","Nazanin","B Nazanin","Mitra","B Mitra","Zar","B Zar",Arial,sans-serif;
    }

    *:not([data-testid="stIconMaterial"]):not(.material-icons):not([class*="material-icons"]){
        font-family: var(--app-font) !important;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"]{
        background: var(--bg-app) !important; color: var(--text-main) !important;
    }
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stText"],
    [data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
    h1,h2,h3,h4,h5,h6,p,label,span,li{ direction: rtl !important; text-align: right !important; }
    [data-baseweb="calendar"] *{ direction: ltr !important; text-align:center !important; }

    /* حذف Deploy / منو / فوتر / نوار وضعیت */
    #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stToolbarActions"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"]{
        display:none !important; visibility:hidden !important; height:0 !important;
    }
    [data-testid="stHeader"]{ background:transparent !important; height:2.2rem !important; }

    /* جلوگیری از کم‌رنگ‌شدن صفحه هنگام کلیک */
    [data-stale="true"], .element-container[data-stale="true"], [data-testid="stAppViewBlockContainer"][data-stale="true"]{
        opacity:1 !important; filter:none !important; transition:none !important;
    }
    .stApp *{ transition:none !important; animation:none !important; }

    /* ============ سایدبار ثابت و بخشی از layout (غیرشناور) ============ */
    [data-testid="stAppViewContainer"]{ direction:rtl !important; display:flex !important; flex-direction:row !important; }
    [data-testid="stSidebar"]{
        position: relative !important;
        inset:auto !important; top:auto !important; right:auto !important; left:auto !important; bottom:auto !important;
        transform:none !important; transition:none !important;
        width:var(--sb-w) !important; min-width:var(--sb-w) !important; max-width:var(--sb-w) !important;
        flex:0 0 var(--sb-w) !important; margin:0 !important;
        background:var(--bg-panel) !important;
        border-left:1px solid var(--border-strong) !important;
        box-shadow:none !important; resize:none !important; overflow-x:hidden !important;
        z-index:1 !important; visibility:visible !important; height:auto !important;
    }
    [data-testid="stSidebar"] > div:first-child{
        width:var(--sb-w) !important; min-width:var(--sb-w) !important; max-width:var(--sb-w) !important;
        transform:none !important; position:relative !important;
    }
    [data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"]{ padding-top:.8rem !important; }
    [data-testid="stSidebar"] *{ direction:rtl !important; text-align:right !important; color:var(--text-main) !important; }

    /* حذف کامل دکمهٔ جمع‌کننده و دستگیرهٔ تغییر اندازه */
    [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarResizeHandle"],
    [data-testid="stSidebarResizer"], [data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"],
    [data-testid="stSidebar"] [class*="esizeHandle"], [data-testid="stSidebar"] [class*="esizer"]{
        display:none !important; visibility:hidden !important; pointer-events:none !important;
        width:0 !important; opacity:0 !important;
    }

    /* محتوای اصلی */
    .main, section.main, [data-testid="stMain"]{ flex:1 1 auto !important; min-width:0 !important; }
    .block-container{ padding-top:3.6rem !important; padding-bottom:3rem !important; max-width:1500px; direction:rtl; }

    .sb-title{
        font-size:.95rem; font-weight:800; color:var(--text-main) !important;
        border-right:4px solid var(--accent); padding-right:9px; margin:.2rem 0 .9rem 0;
    }
    .sb-sep{ height:1px; background:var(--border-soft); margin:1rem 0; }
    .section-title{
        font-size:clamp(.95rem,1.6vw,1.15rem); font-weight:800; color:var(--text-main) !important;
        margin:1.7rem 0 .9rem 0; border-right:4px solid var(--accent); padding-right:10px;
        direction:rtl; text-align:right;
    }

    /* کارت‌ها — بدون سرریز متن */
    .grid-cards{
        display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
        gap:14px; align-items:stretch; margin:0 0 20px 0; width:100%;
    }
    .kpi-card,.feature-card{
        background:var(--bg-card); border:1px solid var(--border-strong); border-radius:16px;
        box-shadow:0 4px 14px rgba(0,0,0,.28); direction:rtl; text-align:right;
        box-sizing:border-box; width:100%; min-width:0; max-width:100%;
        overflow:hidden; display:flex; flex-direction:column; height:100%;
    }
    .kpi-card{ padding:14px 16px; justify-content:center; min-height:116px; }
    .feature-card{ padding:16px; justify-content:flex-start; min-height:150px; }
    .kpi-card *,.feature-card *{
        min-width:0; max-width:100%; overflow-wrap:anywhere; word-break:break-word; white-space:normal;
        text-align:right !important; direction:rtl !important; box-sizing:border-box;
    }
    .kpi-icon,.feature-icon{ font-size:clamp(1.05rem,2vw,1.35rem); line-height:1; margin-bottom:8px; display:block; }
    .kpi-title{ font-size:clamp(.72rem,1.1vw,.86rem); font-weight:700; color:var(--text-muted) !important; margin:0 0 6px; line-height:1.6; }
    .kpi-value{ font-size:clamp(1.05rem,2.2vw,1.6rem); font-weight:900; color:var(--text-main) !important; line-height:1.25; margin:0; }
    .kpi-note{ font-size:clamp(.66rem,1vw,.76rem); color:var(--text-muted) !important; margin-top:6px; line-height:1.7; }
    .feature-title{ font-size:clamp(.85rem,1.4vw,1rem); font-weight:800; color:var(--text-main) !important; margin:0 0 8px; line-height:1.7; }
    .feature-line{ font-size:clamp(.7rem,1.1vw,.82rem); color:var(--text-muted) !important; line-height:1.95; margin:2px 0 0; }
    .kpi-card.is-ok{ border-color:#1F5B45; } .kpi-card.is-warn{ border-color:#5A4319; } .kpi-card.is-danger{ border-color:#5A2530; }

    /* پیام‌ها — کمی پایین‌تر، با مرز کاملاً واضح */
    .msg-spacer{ height:18px; }
    .note-box{
        border-radius:14px; padding:16px 18px; margin:1.5rem 0; line-height:2;
        direction:rtl; text-align:right; font-size:clamp(.78rem,1.2vw,.92rem);
        overflow-wrap:anywhere; box-sizing:border-box; box-shadow:0 3px 12px rgba(0,0,0,.25);
    }
    .note-info{ background:#152238; border:1.5px solid #2E5488; color:#CDE4FF !important; }
    .note-warn{ background:#2E2110; border:1.5px solid #6B5020; color:#FFDCA6 !important; }
    .note-ok{ background:#0F2A21; border:1.5px solid #24704F; color:#A6F2CE !important; }
    .note-danger{ background:#2E1417; border:1.5px solid #6B2C36; color:#FFB9C0 !important; }
    .note-box *{ color:inherit !important; direction:rtl; text-align:right; }
    [data-testid="stAlert"]{
        background:var(--bg-card) !important; border:1.5px solid var(--border-strong) !important;
        border-radius:14px !important; margin:1.4rem 0 !important; padding:15px 18px !important;
    }
    [data-testid="stAlert"] *{ color:var(--text-main) !important; direction:rtl !important; text-align:right !important; }

    /* آپلودر تیره با متن روشن */
    [data-testid="stFileUploader"]{ direction:rtl; }
    [data-testid="stFileUploader"] section, [data-testid="stFileUploaderDropzone"]{
        background:var(--bg-input) !important; border:1.5px dashed var(--border-strong) !important;
        border-radius:12px !important; padding:14px !important;
    }
    [data-testid="stFileUploader"] section *, [data-testid="stFileUploaderDropzone"] *{ color:var(--text-main) !important; }
    [data-testid="stFileUploader"] small, [data-testid="stFileUploaderDropzoneInstructions"] span{ color:var(--text-muted) !important; }
    [data-testid="stFileUploader"] button, [data-testid="stFileUploaderDropzone"] button{
        background:#232B38 !important; color:var(--text-main) !important;
        border:1px solid var(--border-strong) !important; border-radius:10px !important; font-weight:700 !important;
    }
    [data-testid="stFileUploader"] button:hover{ border-color:var(--accent) !important; color:var(--accent) !important; }
    [data-testid="stFileUploaderFile"], [data-testid="stFileUploaderFile"] *{ background:transparent !important; color:var(--text-main) !important; }
    [data-testid="stFileUploaderDeleteBtn"] svg{ fill:var(--accent-danger) !important; }

    /* ویجت‌ها */
    [data-testid="stDateInput"] input{
        direction:ltr !important; text-align:center !important;
        background:var(--bg-input) !important; color:var(--text-main) !important;
    }
    [data-testid="stDateInput"] > div > div{
        background:var(--bg-input) !important; border:1px solid var(--border-strong) !important; border-radius:12px !important;
    }
    [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input{
        background:var(--bg-input) !important; color:var(--text-main) !important;
    }
    [data-testid="stDataFrame"]{ direction:rtl; border-radius:12px; overflow:hidden; border:1px solid var(--border-strong); }
    [data-testid="stDataFrame"] *{ font-family:var(--app-font) !important; }
    .stButton>button,.stDownloadButton>button{
        border-radius:12px !important; border:1px solid var(--border-strong) !important;
        background:#232B38 !important; color:var(--text-main) !important; font-weight:700 !important; width:100%;
    }
    .stButton>button:hover,.stDownloadButton>button:hover{ border-color:var(--accent) !important; color:var(--accent) !important; }
    [data-testid="stExpander"]{ border:1px solid var(--border-strong) !important; border-radius:14px !important; background:var(--bg-card) !important; }
    [data-testid="stExpander"] summary{ direction:rtl; text-align:right; }
    hr{ border-color:var(--border-soft) !important; }

    /* رسپانسیو */
    @media (max-width:1200px){ .grid-cards{ grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); } }
    @media (max-width:992px){
        :root{ --sb-w:265px; }
        .block-container{ padding-left:1rem !important; padding-right:1rem !important; }
        .grid-cards{ grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:12px; }
    }
    @media (max-width:820px){
        [data-testid="stAppViewContainer"]{ flex-direction:column !important; }
        [data-testid="stSidebar"]{
            width:100% !important; min-width:100% !important; max-width:100% !important;
            flex:0 0 auto !important; border-left:none !important; border-bottom:1px solid var(--border-strong) !important;
        }
        [data-testid="stSidebar"] > div:first-child{ width:100% !important; min-width:100% !important; max-width:100% !important; }
        .block-container{ padding-top:1.4rem !important; padding-left:.7rem !important; padding-right:.7rem !important; }
        .grid-cards{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
        .kpi-value{ font-size:clamp(1rem,4.6vw,1.3rem); }
    }
    @media (max-width:480px){
        .grid-cards{ grid-template-columns:1fr; }
        .kpi-card{ min-height:94px; } .feature-card{ min-height:auto; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def section(title: str) -> None:
    st.markdown(
        f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def note(text: str, kind: str = "info", spacer: bool = False) -> None:
    if spacer:
        st.markdown('<div class="msg-spacer"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="note-box note-{kind}">{text}</div>', unsafe_allow_html=True)


# =========================================================
# ۳. ابزار متن و تاریخ (فقط میلادی)
# =========================================================
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value).translate(_DIGITS)
    for old, new in {"ي": "ی", "ك": "ک", "\u200c": " ", "\u200f": "", "\u200e": "",
                     "\ufeff": "", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا"}.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def squeeze(value) -> str:
    return re.sub(r"[\s_\-\.\:\(\)\[\]\/\\،,]+", "", normalize_text(value)).lower()


def clean_display_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        return str(int(value)) if float(value).is_integer() else str(value).strip()
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def canonical_product_key(value) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*(mg|ml|g|iu|میلی گرم|گرم|سی سی)?",
                  " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def format_gregorian(value) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%Y/%m/%d")
    return str(value)


def parse_date_value(value):
    if value is None:
        return pd.NaT
    if isinstance(value, (pd.Timestamp, datetime)):
        try:
            return pd.Timestamp(value).normalize()
        except Exception:
            return pd.NaT
    if isinstance(value, date):
        return pd.Timestamp(value)
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return pd.NaT
            num = float(value)
        except Exception:
            return pd.NaT
        if 20000 < num < 60000:                       # سریال تاریخ اکسل
            return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=num)).normalize()
        return pd.NaT

    text = normalize_text(value)
    if not text or text.lower() in PENDING_MARKERS:
        return pd.NaT
    text = text.replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return pd.Timestamp(datetime.strptime(text, fmt)).normalize()
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, errors="coerce")
        return pd.Timestamp(parsed).normalize() if not pd.isna(parsed) else pd.NaT
    except Exception:
        return pd.NaT


# =========================================================
# ۴. تشخیص هدر و نگاشت هوشمند ستون‌ها
# =========================================================
ALIAS_INDEX: dict[str, str] = {}
for _canon, _aliases in COLUMN_ALIASES.items():
    for _a in [_canon] + _aliases:
        ALIAS_INDEX[squeeze(_a)] = _canon

_TOPICS = {"شیمیای": "chem", "محاسب": "calc", "بسته": "pack", "سبز": "green",
           "رگولاتور": "reg", "بچ": "batch", "سریساخت": "batch", "محصول": "prod", "فراورده": "prod"}


def _phase(s: str) -> str:
    if "شروع" in s:
        return "start"
    if "اتمام" in s or "پایان" in s:
        return "end"
    return ""


def _topic(s: str) -> str:
    for key, val in _TOPICS.items():
        if key in s:
            return val
    return ""


def _compatible(a: str, b: str) -> bool:
    pa, pb = _phase(a), _phase(b)
    if pa and pb and pa != pb:
        return False
    ta, tb = _topic(a), _topic(b)
    if ta and tb and ta != tb:
        return False
    return True


def score_header_cell(cell) -> tuple[str | None, float]:
    s = squeeze(cell)
    if not s or s.startswith("unnamed") or s in {"nan", "none"}:
        return None, 0.0
    if s in ALIAS_INDEX:
        return ALIAS_INDEX[s], 1.0
    best, best_score = None, 0.0
    for key, canon in ALIAS_INDEX.items():
        if not _compatible(s, key):
            continue
        if len(key) >= 6 and (key in s or s in key):
            score = 0.95 - abs(len(s) - len(key)) / 200.0
        else:
            score = SequenceMatcher(None, s, key).ratio() * 0.9
        if score > best_score:
            best, best_score = canon, score
    return (best, best_score) if best_score >= 0.72 else (None, 0.0)


def detect_header_row(raw: pd.DataFrame, max_scan: int = 40) -> int:
    best_idx, best_hits = 0, -1.0
    for i in range(min(max_scan, len(raw))):
        hits = 0.0
        for cell in raw.iloc[i].tolist():
            canon, sc = score_header_cell(cell)
            if canon:
                hits += 1.0 if sc >= 0.95 else 0.6
        if hits > best_hits:
            best_idx, best_hits = i, hits
    return best_idx


def map_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    candidates = []
    for col in df.columns:
        canon, score = score_header_cell(col)
        if canon:
            candidates.append((score, str(col), canon))
    candidates.sort(reverse=True, key=lambda x: (x[0], -len(x[1])))

    used_src, used_dst, rename_map = set(), set(), {}
    for _score, src, canon in candidates:
        if src in used_src or canon in used_dst:
            continue
        rename_map[src] = canon
        used_src.add(src)
        used_dst.add(canon)

    out = df.rename(columns=rename_map)
    out = out.loc[:, ~out.columns.duplicated()]
    return out, {v: k for k, v in rename_map.items()}


@st.cache_data(show_spinner=False)
def load_excel_bytes(file_bytes: bytes, file_name: str):
    """→ dict شامل df، خطا، شمارش‌ها و اطلاعات تشخیص"""
    result = {"df": None, "error": "", "invalid": 0, "total": 0,
              "mapping": {}, "missing_stages": [], "header_row": 0, "headers": [], "sheet": ""}
    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception as exc:
        result["error"] = f"خطا در خواندن فایل اکسل: {exc}"
        return result

    sheet = None
    for name in xl.sheet_names:
        if squeeze(name) == squeeze(SHEET_NAME):
            sheet = name
            break
    if sheet is None:
        for name in xl.sheet_names:
            if squeeze(SHEET_NAME) in squeeze(name):
                sheet = name
                break
    if sheet is None:
        result["error"] = f"شیت «{SHEET_NAME}» یافت نشد. شیت‌های موجود: " + \
            "، ".join(xl.sheet_names)
        return result
    result["sheet"] = sheet

    try:
        raw = xl.parse(sheet, header=None, dtype=object)
    except Exception as exc:
        result["error"] = f"خطا در خواندن شیت «{sheet}»: {exc}"
        return result

    if raw.empty:
        result["error"] = f"شیت «{sheet}» خالی است."
        return result

    header_row = detect_header_row(raw)
    result["header_row"] = header_row
    header_values = [clean_display_value(v)
                     for v in raw.iloc[header_row].tolist()]
    result["headers"] = [h for h in header_values if h]

    df = raw.iloc[header_row + 1:].reset_index(drop=True)
    df.columns = [normalize_text(v) if clean_display_value(v) else f"ستون {i + 1}"
                  for i, v in enumerate(raw.iloc[header_row].tolist())]
    df = df.dropna(axis=1, how="all")

    df, mapping = map_columns(df)
    result["mapping"] = mapping

    if "تاریخ تحویل" not in df.columns:
        result["error"] = ("ستون «تاریخ تحویل» در شیت «" + sheet + "» شناسایی نشد.<br>"
                           "سرستون‌های ردیف شناسایی‌شده: " + "، ".join(result["headers"])[:700])
        return result

    if not any(c in df.columns for c in IDENTITY_COLUMNS):
        result["error"] = ("هیچ‌یک از ستون‌های «نام محصول» یا «شماره بچ» شناسایی نشد.<br>"
                           "سرستون‌های ردیف شناسایی‌شده: " + "، ".join(result["headers"])[:700])
        return result

    for col in IDENTITY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    missing_stages = [c for c in STAGE_COLUMNS if c not in df.columns]
    result["missing_stages"] = missing_stages
    for col in missing_stages:
        df[col] = pd.NaT

    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col].apply(
            parse_date_value), errors="coerce")

    df["نام محصول"] = df["نام محصول"].apply(clean_display_value)
    df["شماره بچ"] = df["شماره بچ"].apply(clean_display_value)

    df = df[ALL_COLUMNS].copy()
    df = df[(df["نام محصول"] != "") | (
        df["شماره بچ"] != "")].reset_index(drop=True)

    result["total"] = len(df)
    result["invalid"] = int(df["تاریخ تحویل"].isna().sum())
    result["df"] = df
    return result


# =========================================================
# ۵. محاسبات
# =========================================================
# جدول  جزئیات کامل بچ‌های بازه

def get_current_stage(row: pd.Series) -> str:
    for col in reversed(STAGE_COLUMNS):
        val = row.get(col)
        if val is not None and not pd.isna(val):
            return col
    return "شروع نشده"


def get_stage_date(row: pd.Series, stage: str):
    if stage == "شروع نشده":
        return row.get("تاریخ تحویل")
    return row.get(stage)


# --- وضعیت‌های رگولاتوری (منبع واحد نام‌ها) ---
REG_NO_GREEN = "برگ سبز صادر نشده"
REG_SENT_EARLY = "ارسال زودتر از مهلت مقرر"
REG_SENT_ON_TIME = "ارسال در مهلت مقرر"
REG_SENT_LATE = "ارسال دیرتر از مهلت مقرر"
REG_WITHIN_DEADLINE = "در مهلت مقرر واقع است"
REG_OVERDUE = "مهلت گذشته (ارسال نشده)"

REG_LATE_STATUSES = [REG_SENT_LATE, REG_OVERDUE]


def regulatory_status(row: pd.Series, today: pd.Timestamp) -> str:
    """
    قاعده: مهلت = تاریخ صدور برگ سبز + REGULATORY_DEADLINE_DAYS روز
      • برگ سبز نداشته باشد            → برگ سبز صادر نشده
      • ارسال شده و قبل از مهلت        → ارسال زودتر از مهلت مقرر
      • ارسال شده و دقیقاً روز مهلت    → ارسال در مهلت مقرر
      • ارسال شده و بعد از مهلت        → ارسال دیرتر از مهلت مقرر
      • ارسال نشده و امروز ≤ مهلت      → در مهلت مقرر واقع است
      • ارسال نشده و امروز > مهلت      → مهلت گذشته (ارسال نشده)
    """
    green = row.get("تاریخ صدور برگ سبز")
    sent = row.get("تاریخ تحویل پرونده به رگولاتوری")

    if pd.isna(green):
        return REG_NO_GREEN

    deadline = green + pd.Timedelta(days=REGULATORY_DEADLINE_DAYS)

    # پرونده ارسال شده است
    if not pd.isna(sent):
        if sent < deadline:
            return REG_SENT_EARLY
        if sent == deadline:
            return REG_SENT_ON_TIME
        return REG_SENT_LATE

    # پرونده هنوز ارسال نشده است؛ خودِ روز آخر مهلت تأخیر محسوب نمی‌شود
    if today <= deadline:
        return REG_WITHIN_DEADLINE
    return REG_OVERDUE


@st.cache_data(show_spinner=False)
def enrich(df: pd.DataFrame, today_ts: pd.Timestamp) -> pd.DataFrame:
    out = df.copy()
    out["مرحله فعلی"] = out.apply(get_current_stage, axis=1)
    out["تاریخ مرحله فعلی"] = out.apply(
        lambda r: get_stage_date(r, r["مرحله فعلی"]), axis=1)
    out["روزهای ماندگاری در مرحله"] = out["تاریخ مرحله فعلی"].apply(  # از تاریخ شروع مرحله فعلی تا امروز چند روز گذشته است؟
        lambda d: int((today_ts - d).days) if not pd.isna(d) else pd.NA
    )
    out["طول کل چرخه (روز)"] = out.apply(
        lambda r: int((r["تاریخ مرحله فعلی"] - r["تاریخ تحویل"]).days)
        if (not pd.isna(r["تاریخ مرحله فعلی"]) and not pd.isna(r["تاریخ تحویل"]))
        else pd.NA, axis=1
    )
    out["وضعیت رگولاتوری"] = out.apply(
        lambda r: regulatory_status(r, today_ts), axis=1)
    out["نام محصول استاندارد"] = out["نام محصول"].apply(canonical_product_key)
    out["تکمیل شده"] = ~out["تاریخ تحویل پرونده به رگولاتوری"].isna()
    return out


# =========================================================
# ۶. سایدبار (منبع داده + خروج همیشه در دسترس)
# =========================================================
with st.sidebar:
    st.markdown('<div class="sb-title">📂 منبع داده</div>',
                unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "فایل اکسل حاوی شیت «محصول»",
        type=["xlsx", "xlsm", "xls"],
        key="excel_file",
        help="فایل باید شامل شیتی با نام «محصول» باشد.",
    )
    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)

    # دکمهٔ خروج — پیش از هر st.stop() ساخته می‌شود، پس همیشه دیده می‌شود
    st.markdown('<div class="sb-title">⏻ پایان کار</div>',
                unsafe_allow_html=True)
    if st.button("🚪 خروج و بستن برنامه", key="exit_app",
                 use_container_width=True):
        st.session_state["_exit_now"] = True
    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)

# --- اجرای فرمان خروج (بلافاصله پس از ساخت سایدبار) ---
if st.session_state.get("_exit_now"):
    import os
    import time
    import threading
    import streamlit.components.v1 as components

    note("برنامه با موفقیت بسته شد. اکنون می‌توانید این پنجرهٔ مرورگر را ببندید. ✅",
         "ok", spacer=True)

    components.html(
        "<script>setTimeout(function(){window.open('','_self');window.close();},700);</script>",
        height=0,
    )

    if not st.session_state.get("_exit_started"):
        st.session_state["_exit_started"] = True

        def _shutdown_process():
            time.sleep(2.0)      # فرصت ارسال پاسخ به مرورگر
            os._exit(0)

        threading.Thread(target=_shutdown_process, daemon=True).start()

    st.stop()

# =========================================================
# ۷. حالت بدون فایل
# =========================================================
if uploaded is None:
    note("برای شروع، فایل اکسل حاوی شیت «محصول» را از سایدبار بارگذاری کنید.",
         "info", spacer=True)
    st.stop()

payload = load_excel_bytes(uploaded.getvalue(), uploaded.name)

if payload["error"]:
    note(payload["error"], "danger", spacer=True)
    st.stop()

data: pd.DataFrame = payload["df"]
invalid_count: int = payload["invalid"]
total_rows: int = payload["total"]

if data.empty:
    note("هیچ ردیف دادهٔ معتبری در شیت «محصول» یافت نشد.", "warn", spacer=True)
    st.stop()

today = date.today()
today_ts = pd.Timestamp(today)
enriched = enrich(data, today_ts)

valid_dates = enriched["تاریخ تحویل"].dropna()
if valid_dates.empty:
    note("هیچ ردیفی با «تاریخ تحویل» معتبر وجود ندارد؛ امکان گزارش‌گیری بازه‌ای نیست.",
         "danger", spacer=True)
    st.stop()

min_date = valid_dates.min().date()
max_date = valid_dates.max().date()
default_start = max(min_date, max_date - timedelta(days=90))

# =========================================================
# ۸. ادامهٔ سایدبار — بازهٔ گزارش، جستجوی محصول و تنظیمات
# =========================================================
with st.sidebar:
    st.markdown('<div class="sb-title">🗓️ بازهٔ گزارش (میلادی)</div>',
                unsafe_allow_html=True)
    start_date = st.date_input(
        "نقطهٔ آغاز گزارش",
        value=default_start, min_value=min_date, max_value=max_date,
        format="YYYY/MM/DD", key="start_date",
    )
    end_date = st.date_input(
        "نقطهٔ پایان گزارش",
        value=max_date, min_value=min_date, max_value=max_date,
        format="YYYY/MM/DD", key="end_date",
    )
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-title">🔍 جستجو بر اساس نام محصول</div>',
                unsafe_allow_html=True)
    all_products = sorted({p for p in enriched["نام محصول"].tolist() if p})
    product_query = ""
    product_options = all_products
    # پاک‌سازی انتخاب‌های قبلی که دیگر در فهرست نیستند (جلوگیری از خطا)
    st.session_state["selected_products"] = [
        p for p in st.session_state.get("selected_products", []) if p in product_options
    ]
    selected_products = st.multiselect(
        "انتخاب محصول (خالی = همهٔ محصولات)",
        options=product_options, key="selected_products",
    )
    st.caption(
        f"محصولات قابل انتخاب: {len(product_options):,} از {len(all_products):,}")
    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-title">⚙️ تنظیمات</div>',
                unsafe_allow_html=True)
    stagnant_days = st.number_input(
        "آستانهٔ راکد بودن (روز)", min_value=1, max_value=365,
        value=DEFAULT_STAGNANT_DAYS, step=1, key="stagnant_days",
    )
    show_invalid_rows = st.checkbox(
        "نمایش ردیف‌های با تاریخ نامعتبر", value=False, key="show_invalid")
    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)
    st.caption(f"فایل: {uploaded.name}")
    st.caption(
        f"شیت: {payload['sheet']} — ردیف هدر: {payload['header_row'] + 1}")
    st.caption(
        f"محدودهٔ داده: {format_gregorian(min_date)} تا {format_gregorian(max_date)}")

# =========================================================
# ۹. فیلتر بازه + فیلتر محصول
# =========================================================

# این کد یک فیلتر (mask) می‌سازد تا فقط ردیف‌هایی را انتخاب کند که تاریخ تحویلشان در بازه زمانی مشخصی قرار دارد.
# mask در اینجا معمولاً یک ستون از مقادیر True/False خواهد بود.
# فقط ردیف‌هایی را انتخاب کن که تاریخ تحویل داشته باشند و تاریخ تحویلشان بین start_date و end_date باشد؛ خود تاریخ شروع و پایان هم شامل بازه هستن

mask = (
    enriched["تاریخ تحویل"].notna()
    & (enriched["تاریخ تحویل"] >= pd.Timestamp(start_date))
    & (enriched["تاریخ تحویل"] <= pd.Timestamp(end_date))
)

if selected_products:
    mask &= enriched["نام محصول"].isin(selected_products)
elif product_query.strip():
    _qq = squeeze(product_query)
    mask &= enriched["نام محصول"].apply(lambda v: _qq in squeeze(v))


# enriched = enrich(data, today_ts)////def enrich(df: pd.DataFrame, today_ts: pd.Timestamp) -> pd.DataFrame:
# filtered = enriched[mask] محصولات/ردیف‌ها را بر اساس mask محدود می‌کند.
filtered = enriched[mask].copy()

active_product_label = (
    "، ".join(selected_products) if selected_products
    else (f"جستجوی «{product_query.strip()}»" if product_query.strip() else "همهٔ محصولات")
)

if payload["missing_stages"]:
    note("ستون‌های زیر در شیت یافت نشدند و خالی در نظر گرفته شدند: "
         + "، ".join(payload["missing_stages"]), "warn", spacer=True)

if invalid_count > 0:
    note(f"تعداد {invalid_count:,} ردیف دارای تاریخ تحویل خالی یا نامعتبر است "
         "و در محاسبات بازهٔ زمانی وارد نشده است.", "warn", spacer=True)

if filtered.empty:
    note(f"در بازهٔ {format_gregorian(start_date)} تا {format_gregorian(end_date)} "
         f"و برای «{active_product_label}» هیچ رکوردی یافت نشد. "
         "لطفاً بازه یا نام محصول را تغییر دهید.", "warn", spacer=True)
    st.stop()
# =========================================================
# ۱۰. شاخص‌های کلیدی — مجموع ۹ ستون شیت «محصول»
# =========================================================
section("📊 شاخص‌های کلیدی بازه")

total_batches = len(filtered)
completed = int(filtered["تکمیل شده"].sum())
in_progress = total_batches - completed
completion_rate = (completed / total_batches * 100) if total_batches else 0.0

stay_series = pd.to_numeric(
    filtered["روزهای ماندگاری در مرحله"], errors="coerce")
cycle_series = pd.to_numeric(filtered["طول کل چرخه (روز)"], errors="coerce")
avg_stay = stay_series.mean()
avg_cycle = cycle_series.mean()
max_stay = stay_series.max()

stagnant_mask = stay_series >= stagnant_days
stagnant_count = int(stagnant_mask.sum())
reg_delay = int(filtered["وضعیت رگولاتوری"].isin(REG_LATE_STATUSES).sum())
unique_products = int(filtered["نام محصول استاندارد"].nunique())

COLUMN_CARDS = [
    ("🔢", "شماره بچ", "شماره بچ"),
    ("🏷️", "نام محصول", "نام محصول"),
    ("📥", "تاریخ تحویل نمونه به آزمایشگاه", "تاریخ تحویل"),
    ("🧪", "تاریخ شروع آزمایشات شیمیایی", "تاریخ شروع آزمایشات شیمیایی"),
    ("✔️", "تاریخ اتمام آزمایشات شیمیایی", "تاریخ اتمام آزمایشات شیمیایی"),
    ("🧮", "تاریخ اتمام کنترل محاسبات", "تاریخ اتمام کنترل محاسبات"),
    ("📦", "تاریخ اتمام بسته‌بندی", "تاریخ اتمام بسته بندی"),
    ("🟢", "تاریخ صدور برگ سبز", "تاریخ صدور برگ سبز"),
    ("📤", "تاریخ تحویل پرونده به رگولاتوری", "تاریخ تحویل پرونده به رگولاتوری"),
]


def column_total(col: str) -> int:
    """مجموع رکوردهای تکمیل‌شدهٔ هر ستون در بازه/محصول انتخابی"""
    series = filtered[col]
    if col in DATE_COLUMNS:
        return int(series.notna().sum())
    return int(series.apply(lambda v: clean_display_value(v) != "").sum())


kpi_rows, cards_html = [], ""
for icon, title, col in COLUMN_CARDS:
    value = column_total(col)
    pct = (value / total_batches * 100) if total_batches else 0.0
    cls = "is-ok" if (value == total_batches and value) else (
        "is-danger" if value == 0 else "is-warn")
    kpi_rows.append({"ستون": title, "مجموع رکوردها": value,
                    "سهم (٪)": round(pct, 1)})
    cards_html += (
        f'<div class="kpi-card {cls}"><span class="kpi-icon">{icon}</span>'
        f'<div class="kpi-title">{title}</div>'
        f'<div class="kpi-value">{value:,}</div>'
        f'<div class="kpi-note">{pct:.1f}٪ از {total_batches:,} ردیف بازه</div></div>'
    )

kpi_df = pd.DataFrame(kpi_rows)
st.markdown(
    f'<div class="grid-cards">{cards_html}</div>', unsafe_allow_html=True)


# =========================================================
# ۱۱. توزیع بچ‌ها بین مراحل
# =========================================================
section("🔬 توزیع بچ‌ها بین مراحل فرآیند")

stage_order = ["شروع نشده"] + STAGE_COLUMNS
stage_counts = filtered["مرحله فعلی"].value_counts()
stage_rows = []
for stage in stage_order:
    count = int(stage_counts.get(stage, 0))
    if count == 0:
        continue
    subset = filtered[filtered["مرحله فعلی"] == stage]
    days = pd.to_numeric(subset["روزهای ماندگاری در مرحله"], errors="coerce")
    stage_rows.append({
        "مرحله": STAGE_LABELS.get(stage, stage),
        "تعداد بچ": count,
        "سهم (٪)": round(count / len(filtered) * 100, 1),
        "میانگین ماندگاری (روز)": round(float(days.mean()), 1) if days.notna().any() else 0.0,
        "بیشترین ماندگاری (روز)": int(days.max()) if days.notna().any() else 0,
    })

stage_df = pd.DataFrame(stage_rows)
col_a, col_b = st.columns([1, 1], gap="medium")
st.dataframe(stage_df, use_container_width=True, hide_index=True)

# =========================================================
# ۱۲. بچ‌های راکد
# =========================================================
section(f"⏳ بچ‌های راکد (بیش از {stagnant_days} روز بدون پیشرفت)")

stagnant_df = filtered[stagnant_mask].copy()
stagnant_export = pd.DataFrame()
if stagnant_df.empty:
    note("هیچ بچ راکدی در این بازه وجود ندارد. ✅", "ok")
else:
    view = stagnant_df.sort_values("روزهای ماندگاری در مرحله", ascending=False)
    show = pd.DataFrame({
        "نام محصول": view["نام محصول"],
        "شماره بچ": view["شماره بچ"],
        "مرحله فعلی": view["مرحله فعلی"].map(lambda s: STAGE_LABELS.get(s, s)),
        "تاریخ تحویل": view["تاریخ تحویل"].apply(format_gregorian),
        "تاریخ آخرین مرحله": view["تاریخ مرحله فعلی"].apply(format_gregorian),
        "روز ماندگاری": view["روزهای ماندگاری در مرحله"],
    })
    stagnant_export = show.copy()

    st.dataframe(show, use_container_width=True, hide_index=True)

# =========================================================
# ۱۳. وضعیت رگولاتوری
# =========================================================
section(
    f"📋 وضعیت ارسال پرونده به رگولاتوری (مهلت {REGULATORY_DEADLINE_DAYS} روز)")

reg_counts = filtered["وضعیت رگولاتوری"].value_counts()
reg_meta = {
    REG_SENT_EARLY: ("⏩", "is-ok"),
    REG_SENT_ON_TIME: ("✅", "is-ok"),
    REG_SENT_LATE: ("⚠️", "is-danger"),
    REG_WITHIN_DEADLINE: ("🕒", "is-warn"),
    REG_OVERDUE: ("🚨", "is-danger"),
    REG_NO_GREEN: ("📄", ""),
}
cards, reg_rows = "", []
for label, (icon, cls) in reg_meta.items():
    count = int(reg_counts.get(label, 0))
    pct = (count / len(filtered) * 100) if len(filtered) else 0.0
    reg_rows.append({"وضعیت": label, "تعداد بچ": count,
                    "سهم (٪)": round(pct, 1)})
    cards += (
        f'<div class="kpi-card {cls}"><span class="kpi-icon">{icon}</span>'
        f'<div class="kpi-title">{label}</div>'
        f'<div class="kpi-value">{count:,}</div>'
        f'<div class="kpi-note">{pct:.1f}٪ از بچ‌های بازه</div></div>'
    )
reg_summary_df = pd.DataFrame(reg_rows)
st.markdown(f'<div class="grid-cards">{cards}</div>', unsafe_allow_html=True)

late_export = pd.DataFrame()
late_df = filtered[filtered["وضعیت رگولاتوری"].isin(REG_LATE_STATUSES)]
if not late_df.empty:
    lv = late_df.copy()
    lv["روز تأخیر"] = lv.apply(
        lambda r: int(((r["تاریخ تحویل پرونده به رگولاتوری"] if pd.notna(r["تاریخ تحویل پرونده به رگولاتوری"]) else today_ts)
                       - r["تاریخ صدور برگ سبز"]).days) - REGULATORY_DEADLINE_DAYS,
        axis=1,
    )
    late_export = pd.DataFrame({
        "نام محصول": lv["نام محصول"],
        "شماره بچ": lv["شماره بچ"],
        "تاریخ برگ سبز": lv["تاریخ صدور برگ سبز"].apply(format_gregorian),
        "تاریخ ارسال": lv["تاریخ تحویل پرونده به رگولاتوری"].apply(format_gregorian),
        "وضعیت": lv["وضعیت رگولاتوری"],
        "روز تأخیر": lv["روز تأخیر"],
    }).sort_values("روز تأخیر", ascending=False)
    with st.expander(f"مشاهدهٔ {len(late_df):,} پروندهٔ دارای تأخیر رگولاتوری"):
        st.dataframe(late_export, use_container_width=True, hide_index=True)

# =========================================================
# ۱۴. تحلیل محصولات
# =========================================================
section("🧪 تحلیل بر اساس محصول")

prod = filtered.groupby("نام محصول استاندارد").agg(
    تعداد_بچ=("شماره بچ", "count"),
    تکمیل_شده=("تکمیل شده", "sum"),
    میانگین_چرخه=("طول کل چرخه (روز)", lambda s: pd.to_numeric(
        s, errors="coerce").mean()),
    میانگین_ماندگاری=("روزهای ماندگاری در مرحله",
                      lambda s: pd.to_numeric(s, errors="coerce").mean()),
).reset_index()
prod = prod[prod["نام محصول استاندارد"] != ""]
prod["نرخ تکمیل (٪)"] = (prod["تکمیل_شده"] / prod["تعداد_بچ"] * 100).round(1)
prod["میانگین_چرخه"] = prod["میانگین_چرخه"].round(1)
prod["میانگین_ماندگاری"] = prod["میانگین_ماندگاری"].round(1)
prod = prod.rename(columns={
    "نام محصول استاندارد": "نام محصول", "تعداد_بچ": "تعداد بچ", "تکمیل_شده": "تکمیل‌شده",
    "میانگین_چرخه": "میانگین چرخه (روز)", "میانگین_ماندگاری": "میانگین ماندگاری (روز)",
}).sort_values("تعداد بچ", ascending=False)

st.markdown(
    f"""
<div class="grid-cards">
  <div class="kpi-card"><span class="kpi-icon">🏭</span>
    <div class="kpi-title">تعداد محصولات منحصربه‌فرد</div>
    <div class="kpi-value">{unique_products:,}</div>
    <div class="kpi-note">در بازهٔ انتخابی</div></div>
  <div class="kpi-card"><span class="kpi-icon">🥇</span>
    <div class="kpi-title">پرتکرارترین محصول</div>
    <div class="kpi-value">{(prod.iloc[0]["نام محصول"] if not prod.empty else "—")}</div>
    <div class="kpi-note">{(int(prod.iloc[0]["تعداد بچ"]) if not prod.empty else 0):,} بچ</div></div>
  <div class="kpi-card"><span class="kpi-icon">⏱️</span>
    <div class="kpi-title">کندترین محصول (میانگین چرخه)</div>
    <div class="kpi-value">{(prod.sort_values("میانگین چرخه (روز)", ascending=False).iloc[0]["نام محصول"] if not prod.empty else "—")}</div>
    <div class="kpi-note">{(prod["میانگین چرخه (روز)"].max() if not prod.empty else 0)} روز</div></div>
</div>
""",
    unsafe_allow_html=True,
)
st.dataframe(prod, use_container_width=True, hide_index=True)

# =========================================================
# ۱۵. جدول جزئیات
# =========================================================
section("📄 جزئیات کامل بچ‌های بازه")

detail = filtered.sort_values("تاریخ تحویل", ascending=False).copy()
detail_view = pd.DataFrame(
    {"نام محصول": detail["نام محصول"], "شماره بچ": detail["شماره بچ"]})
for col in DATE_COLUMNS:
    detail_view[col] = detail[col].apply(format_gregorian)
detail_view["مرحله فعلی"] = detail["مرحله فعلی"].map(
    lambda s: STAGE_LABELS.get(s, s))
detail_view["روز ماندگاری"] = detail["روزهای ماندگاری در مرحله"]
detail_view["طول چرخه (روز)"] = detail["طول کل چرخه (روز)"]
detail_view["وضعیت رگولاتوری"] = detail["وضعیت رگولاتوری"]

st.dataframe(detail_view, use_container_width=True,
             hide_index=True, height=440)

if show_invalid_rows and invalid_count > 0:
    with st.expander(f"ردیف‌های با تاریخ تحویل نامعتبر ({invalid_count:,} ردیف)"):
        inv = enriched[enriched["تاریخ تحویل"].isna()].copy()
        inv_view = pd.DataFrame(
            {"نام محصول": inv["نام محصول"], "شماره بچ": inv["شماره بچ"]})
        for col in STAGE_COLUMNS:
            inv_view[col] = inv[col].apply(format_gregorian)
        st.dataframe(inv_view, use_container_width=True, hide_index=True)


# =========================================================
# ۱۶. سایر قابلیت‌ها
# =========================================================
section("🧰 سایر قابلیت‌ها")

st.markdown(
    f"""
<div class="grid-cards">
  <div class="feature-card">
    <div class="feature-title">قواعد محاسبه</div>
    <div class="feature-line">مرحلهٔ فعلی = آخرین تاریخ ثبت‌شدهٔ فرآیند</div>
    <div class="feature-line">مهلت رگولاتوری = {REGULATORY_DEADLINE_DAYS} روز پس از صدور برگ سبز</div>
    <div class="feature-line">تمام تاریخ‌ها میلادی (YYYY/MM/DD)</div>
  </div>
  <div class="feature-card"><span class="feature-icon">📅</span>
    <div class="feature-title">بازهٔ جاری گزارش</div>
    <div class="feature-line">از {format_gregorian(start_date)} تا {format_gregorian(end_date)}</div>
    <div class="feature-line">تعداد رکورد در بازه: {len(filtered):,}</div>
    <div class="feature-line">تاریخ امروز: {format_gregorian(today)}</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


def _safe_sheet(name: str) -> str:
    for ch in "[]:*?/\\":
        name = name.replace(ch, "-")
    return name[:31]


EXPORT_BLOCKS = [
    ("جزئیات کامل بچ‌های بازه", detail_view, None),
    ("تحلیل بر اساس محصول", prod, None),
    (f"وضعیت رگولاتوری (مهلت {REGULATORY_DEADLINE_DAYS} روز)",
     reg_summary_df, late_export),
    (f"بچ‌های راکد (بیش از {stagnant_days} روز)", stagnant_export, None),
    ("توزیع بچ‌ها بین مراحل فرآیند", stage_df, None),
]


def _frame_or_empty(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    return pd.DataFrame({"وضعیت": ["موردی یافت نشد"]})


def build_excel(blocks) -> bytes:
    buffer = io.BytesIO()
    engine = None
    for candidate in ("xlsxwriter", "openpyxl"):
        try:
            __import__(candidate)
            engine = candidate
            break
        except ImportError:
            continue
    with pd.ExcelWriter(buffer, engine=engine) as writer:
        for name, main_df, extra_df in blocks:
            sheet = _safe_sheet(name)
            main = _frame_or_empty(main_df)
            main.to_excel(writer, sheet_name=sheet, index=False)
            if isinstance(extra_df, pd.DataFrame) and not extra_df.empty:
                extra_df.to_excel(writer, sheet_name=sheet,
                                  index=False, startrow=len(main) + 3)
    return buffer.getvalue()


def build_csv_zip(blocks) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, main_df, extra_df in blocks:
            content = _frame_or_empty(main_df).to_csv(index=False)
            if isinstance(extra_df, pd.DataFrame) and not extra_df.empty:
                content += "\n\n" + extra_df.to_csv(index=False)
            zf.writestr(f"{_safe_sheet(name)}.csv",
                        content.encode("utf-8-sig"))
    return buffer.getvalue()


# ---------- خروجی‌ها: ساخت یک‌باره و دانلود پایدار ----------
stamp = f"{start_date:%Y%m%d}_{end_date:%Y%m%d}"
export_signature = f"{stamp}|{active_product_label}|{stagnant_days}|{len(filtered)}"

if "export_cache" not in st.session_state:
    st.session_state["export_cache"] = {}

cache = st.session_state["export_cache"]
is_ready = cache.get("sig") == export_signature

col_make, col_dl, col_csv = st.columns(3, gap="medium")

with col_make:
    if st.button("🧾 آماده‌سازی فایل‌های خروجی", key="prepare_exports",
                 use_container_width=True):
        try:
            st.session_state["export_cache"] = {
                "sig": export_signature,
                "xlsx": build_excel(EXPORT_BLOCKS),
                "zip": build_csv_zip(EXPORT_BLOCKS),
            }
        except Exception as exc:
            st.session_state["export_cache"] = {}
            note(f"امکان ساخت فایل خروجی نبود ({exc}).", "warn")
        cache = st.session_state["export_cache"]
        is_ready = cache.get("sig") == export_signature

with col_dl:
    if is_ready and cache.get("xlsx"):
        st.download_button(
            "📥 دانلود گزارش اکسل (۵ شیت)",
            data=cache["xlsx"],
            file_name=f"lab_report_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_excel_main",
        )
    else:
        st.button("📥 دانلود گزارش اکسل (۵ شیت)", key="dl_xlsx_off",
                  disabled=True, use_container_width=True)

with col_csv:
    if is_ready and cache.get("zip"):
        st.download_button(
            "📄 دانلود CSV (۵ فایل در یک ZIP)",
            data=cache["zip"],
            file_name=f"lab_report_csv_{stamp}.zip",
            mime="application/zip",
            use_container_width=True,
            key="download_csv_main",
        )
    else:
        st.button("📄 دانلود CSV (۵ فایل در یک ZIP)", key="dl_csv_off",
                  disabled=True, use_container_width=True)

if not is_ready:
    note("برای دریافت خروجی، ابتدا دکمهٔ «آماده‌سازی فایل‌های خروجی» را بزنید. "
         "پس از هر تغییر در بازه یا محصول، دوباره این دکمه را بزنید.", "info")

# =========================================================
# ۱۷. خروج از برنامه → به بلاک ۶ منتقل شد (سایدبار)
# =========================================================

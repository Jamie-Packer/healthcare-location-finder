"""Load the web fonts and the small amount of CSS the theme file cannot express."""

import streamlit as st

FONTS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Fraunces:opsz,wght@9..144,400;9..144,600"
    "&family=Inter:wght@400;500;600&display=swap"
)

CSS = f"""
<style>
@import url('{FONTS_URL}');

.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea {{
    font-family: Inter, system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
.stApp h1, .stApp h2, .stApp h3, summary {{
    font-family: Fraunces, Georgia, 'Times New Roman', serif;
    letter-spacing: -0.01em;
}}
.stApp :not(pre) > code {{ color: #e0b867; }}
.stApp pre code span {{ color: #ece6da !important; }}
.stApp h1 {{ font-weight: 600; margin-bottom: 0.25rem; }}
.stApp .block-container {{
    max-width: 1100px;
    padding-top: 3rem;
}}
@media (max-width: 640px) {{
    .stApp h1 {{ font-size: 1.9rem; }}
    .stApp .block-container {{ padding-top: 1.5rem; }}
}}
.version {{
    color: #b9b1a2;
    font-size: 0.8rem;
    letter-spacing: 0.06em;
    margin: 0.15rem 0 0.4rem 0;
}}
.lede {{
    color: #ece6da;
    font-size: 1.05rem;
    margin: 0 0 1.5rem 0;
}}

/* How to use */
.stApp [data-testid="stExpander"] details {{
    border: 1px solid #3b362e;
    border-radius: 0.75rem;
    background: #211e1a;
}}
.stApp [data-testid="stExpander"] summary {{
    font-size: 1.1rem;
    padding: 0.75rem 1rem;
}}
.stApp [data-testid="stExpander"] summary:hover {{
    color: #d4a24c;
}}

/* Result summary */
.summary {{
    border-left: 3px solid #d4a24c;
    padding: 0.15rem 0 0.15rem 0.9rem;
    margin: 1rem 0 0.75rem 0;
    font-family: Fraunces, Georgia, serif;
    font-size: 1.25rem;
}}
.summary span {{ color: #b9b1a2; font-family: Inter, system-ui, sans-serif; font-size: 0.95rem; }}

.stApp [data-testid="stDataFrame"] {{
    border: 1px solid #3b362e;
    border-radius: 0.75rem;
    overflow: hidden;
}}
</style>
"""


def apply_theme() -> None:
    st.html(CSS)

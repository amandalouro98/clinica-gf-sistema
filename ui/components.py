import streamlit as st
from datetime import datetime

def header_titulo(titulo: str, subtitulo: str = ""):
    sub_html = f"<div class='subtitle'>{subtitulo}</div>" if subtitulo else ""
    st.markdown(f"""
    <div class="gf-page-title">
        <h2>{titulo}</h2>
        {sub_html}
    </div>
    <div class="gf-divider"></div>
    """, unsafe_allow_html=True)

def month_from_date(d):
    return datetime.strftime(d, "%Y-%m")

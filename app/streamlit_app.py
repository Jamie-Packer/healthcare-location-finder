"""Open the location search, with a separate help page."""

import streamlit as st

st.set_page_config(page_title="Healthcare location reference", layout="wide")

st.navigation(
    [
        st.Page("search.py", title="Search", default=True),
        st.Page("help.py", title="Help"),
    ],
    position="hidden",
).run()

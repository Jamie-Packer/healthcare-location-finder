"""Open the location search, with a separate help page."""

import streamlit as st

st.set_page_config(page_title="Healthcare location reference", layout="wide")


def _version_tuple(text: str) -> tuple[int, ...]:
    numbers = []
    for part in text.split("."):
        digits = "".join(character for character in part if character.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers)


if _version_tuple(st.__version__) < (1, 48):
    st.error(
        f"Streamlit {st.__version__} is too old for this app. "
        "It needs 1.48 or newer, from this project's virtual environment. "
        "The README run command is the one that works."
    )
    st.stop()

st.navigation(
    [
        st.Page("search.py", title="Search", default=True),
        st.Page("help.py", title="Help"),
    ],
    position="hidden",
).run()

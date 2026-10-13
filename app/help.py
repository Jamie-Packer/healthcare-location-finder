"""Explain how to search, what the files contain, and what each column means."""

import streamlit as st

from data import SAMPLE_WARNING, attribution_markdown, attribution_year, currency_markdown, ensure_data


try:
    paths = ensure_data()
except FileNotFoundError as exc:
    st.title("Full guide")
    st.error(str(exc))
    st.stop()

st.title("Full guide")
if paths.source == "sample":
    st.warning(SAMPLE_WARNING)
if st.button("Back to search"):
    st.switch_page("search.py")

st.header("How to use it")
st.markdown(
    """
Type a place or a name and press Enter. You can search by county, trust,
hospital, postcode, ODS code or CQC location id. (ODS is the NHS Organisation
Data Service. CQC is the Care Quality Commission.)

1. **Pick a match.** The list shows up to 30 results. A result can be a country,
   region, county, local authority, integrated care board (ICB), provider or a
   single site. The table then lists the current sites under it.
2. **Choose services.** Leave the service filter empty to see every site. Select
   one or more of hospital, care home, GP and other to narrow the table.
3. **Download the table.** The screen shows the first 500 sites. **Prepare
   download** builds a CSV, plus an Excel file when the extract is small enough.
   Both include every site in your selection, one row per site.

Counties follow the county boundary, so Kent does not include Medway. Medway is
its own unitary authority. The Kent and Medway ICB covers both.

**`match_string` is the last column in that file.** It is one line of keywords
for a site: its names, parent organisation, town, postcode (with and without
the space) and codes. Punctuation and common words such as hospital, NHS and
trust are removed.
"""
)

st.header("What you can and cannot find")
st.markdown(
    """
**Included: current sites in England**

- NHS trusts and independent healthcare providers, with their sites (ODS).
- Every location registered with the CQC, including care homes, hospitals, GP
  practices and other services.
- The local authority, county, region and ICB for each postcode.

**Not included yet**

- Scotland, Wales and Northern Ireland.
- Closed or deactivated sites, and older names. You cannot look up a site as it
  was in the past.
- Mergers and renames. A renamed organisation is not linked to the one it
  replaced.
- Free-text matching. The app finds places in this register. It does not
  compare a sentence from another system. Download the table and match it
  elsewhere.
- Named people, such as registered managers.
- NHS GP lists, schools, prisons and Welsh health boards. A GP practice appears
  only if the CQC registers that location.

**How services are decided**

- **Hospital:** the name or CQC category contains "hospital".
- **Care home:** the CQC care-home flag is yes.
- **GP:** the CQC category is a GP practice.
- **Other:** everything else that is open, such as clinics and offices whose
  names do not say hospital.

**Why a site can appear twice**

A CQC location is joined to an ODS site only when its location ODS code matches
exactly one open ODS site. If that code is blank, both rows stay. Some NHS
hospitals, such as William Harvey Hospital, keep their ODS code in the CQC
location id and leave the ODS code blank, so they show up as two rows.
"""
)

st.header("How current the data is")
st.markdown(currency_markdown(paths))

st.header("Sources and licence")
st.markdown(attribution_markdown(attribution_year(paths.manifest)))

st.header("Columns")
st.markdown(
    """
| Column | Meaning |
| --- | --- |
| `name` | Site name. When ODS and CQC records are combined, the CQC name is kept. |
| `parent_name` | Organisation that runs the site: the ODS parent, or the CQC provider when there is no ODS parent. |
| `postcode` | Site postcode. |
| `town` | Town or city from the address. |
| `local_authority` | Local authority for the postcode. If the postcode is not in the postcode lookup, the CQC value is used. |
| `region` | Region for the postcode, with the same CQC fallback. |
| `icb` | Integrated care board for the postcode, the NHS commissioning area for that address. It is not always the organisation that runs the site. |
| `ods_code` | ODS code, when the site is on the ODS list. |
| `cqc_location_id` | CQC location id, when the site is on the CQC register. |
| `service_type` | `hospital`, `care home`, `gp` or `other`. |
| `valid_from` | Start date from the source: the CQC registration date, or the ODS legal start date for sites only on the ODS list. The CQC date wins when both exist. |
| `valid_to` | End date. Blank means the site is still open. Closed sites are not listed, so this column is empty for now. |
| `match_string` | Upper-case keywords with punctuation and common words removed: site name, ODS name, brand, parent, town, postcode with and without the space, ODS code and CQC location id. |
"""
)

"""Explain how to search, what the files contain, and what each column means."""

import streamlit as st

from data import SAMPLE_WARNING, attribution_markdown, attribution_year, currency_markdown, ensure_data


try:
    paths = ensure_data()
except FileNotFoundError as exc:
    st.title("Help")
    st.error(str(exc))
    st.stop()

st.title("Help")
if paths.source == "sample":
    st.warning(SAMPLE_WARNING)
if st.button("Back to search"):
    st.switch_page("search.py")

st.header("How to use it")
st.markdown(
    """
Type a place, then press Enter. A name or a code both work: a county, an
integrated care board, a trust, a hospital, a postcode, an Organisation Data
Service code, or a Care Quality Commission location id.

**Matching places** lists up to 30 hits. Pick one. The choice can be a
country, region, county, local authority, integrated care board, provider, or
a single site. The table then lists the current sites under that place.

**Service** keeps every site, or limits the table to hospital, care home, GP,
or other.

A county uses the county boundary. Kent does not include Medway, because
Medway is a unitary authority. The Kent and Medway integrated care board does
include Medway.

The table on screen shows the first 500 sites. The keyword box shows the first
200 strings. **Prepare download** builds a CSV, and an Excel file when the
extract is not too large. Those files include every site in the current filter.

`match_string` is the column to copy. It is one line of keywords for that
site: names, the parent organisation, the town, the postcode with and without
a space, and the organisation codes. Punctuation is removed.
"""
)

st.header("What you can and cannot find")
st.markdown(
    """
The search covers current sites in England:

- NHS trusts and their sites, and independent providers and their sites, from
  the Organisation Data Service.
- Locations registered with the Care Quality Commission, including care homes,
  hospitals, GP practices, and other registered services.
- The local authority, county, region, and integrated care board for the
  postcode.

It does not cover:

- Scotland, Wales, or Northern Ireland. A site outside England is left out.
- Closed sites, or Care Quality Commission locations that have been
  deactivated. There is no way to look up an older name or a previous
  organisation.
- Mergers and successor organisations. A rename is not linked back to the
  organisation it replaced.
- NHS GP lists, schools, prisons, or Welsh health boards. A GP practice
  appears only when the Care Quality Commission registers that location.
- Named people, such as a registered manager.
- Free-text matching. The app finds places in this register. It does not
  compare a sentence from another system. Copy `match_string` when you need
  the keywords elsewhere.

**Hospital** means the name or the Care Quality Commission category contains
"hospital". **Care home** means the Care Quality Commission care-home flag is
yes. **GP** means the category is a GP practice. Every other open site is
**other**, including clinics and offices whose names do not say hospital.

One real building can be two rows. A Care Quality Commission location is
combined with an Organisation Data Service site only when its location ODS
code matches exactly one open site. If that code is blank, the two records
stay separate. Some NHS hospitals store the ODS code in the Care Quality
Commission location id and leave the ODS code blank, so both rows remain.
"""
)

st.header("How current the data is")
st.markdown(currency_markdown(paths))
st.markdown(
    """
The Organisation Data Service reports are the England trust, trust site, and
independent provider files as they stood when they were downloaded.
"""
)

st.header("Sources and licence")
st.markdown(attribution_markdown(attribution_year(paths.manifest)))

st.header("Columns")
st.markdown(
    """
| Column | Meaning |
| --- | --- |
| `name` | Site name. Where the two sources are combined, the Care Quality Commission name is kept. |
| `match_string` | Keywords in upper case, with punctuation removed: site name, Organisation Data Service name, brand, parent, town, postcode with and without a space, ODS code, and Care Quality Commission location id. |
| `parent_name` | Organisation that operates the site. This is the Organisation Data Service parent, or the Care Quality Commission provider when there is no parent on that list. |
| `postcode` | Site postcode. |
| `town` | Town or city from the address. |
| `local_authority` | Local authority for the postcode. If the postcode is missing from the postcode lookup, the Care Quality Commission local authority is used instead. |
| `region` | Region for the postcode. If the postcode is missing from the postcode lookup, the Care Quality Commission region is used instead. |
| `icb` | Integrated care board for the postcode: the NHS commissioning area that covers that address. It is not always the organisation that runs the site. |
| `ods_code` | Organisation Data Service code, when the site is on that list. |
| `cqc_location_id` | Care Quality Commission location id, when the site is on that register. |
| `service_type` | `hospital`, `care home`, `gp`, or `other`. |
| `valid_from` | Start date recorded by the source. For a Care Quality Commission location this is the registration start date. For a site that exists only on the Organisation Data Service list, this is the legal start date. Where both exist, the registration start date is kept. |
| `valid_to` | End date. Blank means the site is still open in this file. Closed sites are not listed, so this column is empty in the current download. |
"""
)

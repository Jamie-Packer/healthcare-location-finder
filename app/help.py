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
if st.button("Back to search", icon=":material/arrow_back:"):
    st.switch_page("search.py")

st.header("How to use it")
st.markdown(
    """
1. **Choose a country or search.** Open **Country** and pick England, Scotland,
   Wales, Northern Ireland or the United Kingdom. The United Kingdom lists every
   site, so the download is one file. You can do this without typing a place.
   Or type a place or a name and press Enter. That can be a county, a trust, a
   health board, a hospital, a postcode, an NHS code or a regulator id. NHS codes
   come from the Organisation Data Service or Public Health Scotland. Regulator
   ids come from the Care Quality Commission, Care Inspectorate Wales, the Care
   Inspectorate or RQIA.
2. **Pick a place.** If you searched, the list shows up to 30 results. A place
   can be a country, region, county, local authority, integrated care board,
   health board, HSC trust area, provider or single site. The table then lists
   the current sites under it. A country chosen above narrows this list. Clear
   **Country** to keep every country in that place.
3. **Narrow it down.** Leave **Service** empty to keep every service, or pick
   the ones you want. **Columns** changes what the table and the download show,
   and **Default columns** puts the usual set back.
4. **Download.** The screen shows the first 500 sites. **Prepare download**
   builds a CSV, plus an Excel file when the extract is small enough. Both include
   every site in your selection, one row per site.

Counties and regions are only filled in England. Kent does not include Medway,
which is its own unitary authority, but the Kent and Medway integrated care board
covers both.

**The keyword string.** `match_string` is left out of the default columns. Add it
under **Columns** to include it, and it is then the last column. It holds one
line of keywords for each site: its names, parent organisation, town, postcode
(with and without the space) and codes. Punctuation and common words such as
hospital, NHS and trust are removed. The street address is left out.
"""
)

st.header("What you can and cannot find")
st.markdown(
    """
**Included: current sites in England, Wales, Scotland and Northern Ireland**

- **England:** NHS trusts and independent healthcare providers with their sites,
  and every location registered with the Care Quality Commission.
- **Wales:** health boards and their sites, GP practices, and adult services
  registered with Care Inspectorate Wales. Velindre and Welsh Ambulance Service
  sites come from the NHS site list.
- **Scotland:** NHS hospitals and GP practices from Public Health Scotland, and
  adult services registered with the Care Inspectorate.
- **Northern Ireland:** GP practices, adult services registered with RQIA, and a
  checked list of HSC hospitals. The hospital list is not a live feed, and the
  build warns when one of its postcodes is retired.
- **Every site:** the local authority for its postcode, and a health area. That is
  an integrated care board in England, a health board in Wales and Scotland, or an
  HSC trust area in Northern Ireland.

Country, local authority and health area all come from the postcode. A service
registered in one country with an office over the border appears under the
country of its office.

**Known gaps**

- Independent hospitals and clinics in Wales and Scotland. Healthcare
  Inspectorate Wales and Healthcare Improvement Scotland do not publish a bulk list.
- Community sites in Northern Ireland. There is no open list of them, and the
  hospital list cannot tell when a hospital closes.
- Welsh branch surgeries, which are not in the GP practice file.
- Pharmacies and dental practices as their own category. A dental service
  registered as a care location is listed as other.
- Closed sites and older names. You cannot look up a site as it was in the past.
- Mergers and renames. A renamed organisation is not linked to the one it replaced.
- Named people, such as registered managers.

**How services are decided**

- **Hospital:** the name or the source category says hospital. A dental service
  registered under an independent-hospital heading stays other. In Northern
  Ireland most registered independent hospitals are laser and skin clinics, so
  only those with hospital in the name count.
- **Care home:** a care home for adults, with or without nursing.
- **GP:** a GP practice.
- **Home care:** the postcode is an office and the care happens elsewhere. That
  covers domiciliary care, nurse agencies and supported living, including
  community-based adult social care in England.
- **Other:** clinics, offices and any other registered service in scope.

**Why a site can appear twice**

In England, a Care Quality Commission location is joined to an NHS site only when
its organisation code matches exactly one open site. If that code is blank, both
rows stay. Some NHS hospitals keep their organisation code in the regulator id
and leave the organisation code blank, so they appear twice. Wales, Scotland and
Northern Ireland are not merged across sources, so two sources can list the same
place.
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
| `name` | Site name. When an England NHS site and a Care Quality Commission record are combined, the Care Quality Commission name is kept. |
| `parent_name` | Organisation that runs the site: the NHS parent, the health board, or the registered provider. |
| `address` | Street address. It is not part of the keyword string. |
| `town` | Town or city. |
| `postcode` | Site postcode. |
| `country` | England, Wales, Scotland or Northern Ireland, from the postcode. |
| `local_authority` | Local authority for the postcode. For an England site missing from the postcode lookup, the Care Quality Commission value is used. |
| `county` | County for an England postcode. Blank elsewhere. |
| `region` | Region for an England postcode. Blank elsewhere. |
| `health_area` | Integrated care board, health board or HSC trust area. Usually from the postcode, so it may not be the organisation that runs the site. |
| `nhs_code` | NHS organisation code from the Organisation Data Service or Public Health Scotland, when the site has one. |
| `regulator` | Care Quality Commission, CIW, Care Inspectorate or RQIA, when the site comes from that register. |
| `regulator_id` | The id on that register. |
| `service_type` | `hospital`, `care home`, `gp`, `home care` or `other`. |
| `source` | The register the row came from. `ods+cqc` means the England records were combined. |
| `valid_from` | Start date from the source, where the publisher gives one. |
| `valid_to` | End date. Blank means the site is open. Closed sites are not listed yet, so this is always blank for now. |
| `match_string` | Optional. Upper-case keywords with punctuation and common words removed: site name, other names, parent, town, postcode with and without the space, NHS code and regulator id. When included, it is the last column. |

More columns, such as codes for each area, are available under **Columns** on the search page.
"""
)

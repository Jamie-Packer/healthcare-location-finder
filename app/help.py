"""Explain how to search, what the files contain, and what each column means."""

from pathlib import Path

import streamlit as st

from data import (
    SAMPLE_WARNING,
    STALE_CACHE_WARNING,
    attribution_markdown,
    attribution_year,
    currency_markdown,
    ensure_data,
)


def _relationship_diagram() -> None:
    st.iframe(Path(__file__).resolve().parent / "assets" / "relationships.html", height=780)


try:
    paths = ensure_data()
except FileNotFoundError as exc:
    st.title("Full guide")
    st.error(str(exc))
    st.stop()

st.title("Full guide")
if paths.source == "sample":
    st.warning(SAMPLE_WARNING)
elif paths.source == "stale_cache":
    st.warning(STALE_CACHE_WARNING)
if st.button("Back to search", icon=":material/arrow_back:"):
    st.switch_page("search.py")

st.header("How to use it")
st.markdown(
    """
1. **Choose a country or search.** Open **Country** and pick England, Scotland,
   Wales, Northern Ireland or the United Kingdom. The United Kingdom lists every
   site, so the download is one file. You can browse by country without typing a
   search. Or type a place, name, brand, postcode, NHS code or regulator id and
   press Enter.
2. **Pick a place.** Search matches display names, brand names, alternative
   names, postcodes and codes, and returns up to 30 places that fit your active
   **Country** and **Service** filters. A place can be a country, region, county,
   local authority, integrated care board, health board, HSC trust area,
   provider or single site. Clear **Country** to search across the whole UK.
3. **Narrow it down.** Leave **Service** empty to include every service type, or
   select one or more types. Open **Columns** to choose which fields appear in
   the table and download, and use **Default columns** to restore the standard
   set.
4. **Download.** The table previews the first 500 sites. Select **Prepare
   download** to build a CSV (and an Excel file for extracts up to 200,000 rows).
   Downloads include every site matching your selection, one row per site.

**Geography note.** Counties and regions are populated for England only. English
unitary authorities sit outside counties — for example, Kent does not include
Medway, though the Kent and Medway integrated care board covers both.

**The keyword string.** `match_string` is left out of the default columns. Add it
under **Columns** to include it as the final column. It combines each site's
names, parent organisation, town, postcode (with and without spaces) and codes
into one upper-case line with punctuation and common words (such as *hospital*,
*NHS* and *trust*) removed. Street addresses are excluded.
"""
)

st.header("What you can and cannot find")
st.markdown(
    """
**Included: current sites across the UK**

- **England:** NHS trusts, independent healthcare providers and their sites from
  NHS England (ODS), plus all active locations registered with the Care Quality
  Commission (CQC).
- **Wales:** NHS health boards and their sites (including Velindre and Welsh
  Ambulance Service), GP practices, and regulated adult social care services
  from Care Inspectorate Wales (CIW).
- **Scotland:** NHS hospitals and GP practices from Public Health Scotland (PHS),
  and active regulated adult services from the Care Inspectorate.
- **Northern Ireland:** GP practices from ODS, regulated adult services from
  RQIA, and a checked list of HSC hospitals. The hospital list is maintained
  with this reference rather than drawn from a live feed; the build warns if any
  of its postcodes are retired.
- **Geography on every site:** Country, local authority and health area
  (integrated care board in England, health board in Wales and Scotland, or HSC
  trust area in Northern Ireland) come from the ONS postcode lookup, with
  source-record health boards/trust areas used where published. A service whose
  registered address sits across a national border appears under the country of
  its postcode.

**Known gaps**

- **Independent hospitals and clinics in Wales and Scotland:** Healthcare
  Inspectorate Wales and Healthcare Improvement Scotland do not publish bulk
  open registers.
- **Northern Ireland community estate:** No open register is published, and the
  checked HSC hospital list does not automatically detect closures.
- **Welsh branch surgeries:** Not published in the GP practice file.
- **Pharmacies and standalone dental practices:** Not included as separate
  service categories (dental services registered as care locations appear under
  `other`).
- **Historical records:** Closed sites, former names, past organisational
  ownership and merger histories are not searchable.
- **Personal data:** Named individuals (such as registered managers) are stripped
  at ingest and never stored.

NHS trusts, health boards and HSC trusts with zero current sites are retained in
the downloadable reference bundle (`location-reference-bundle.zip`), while this
app lists places with at least one current site.

**How service types are classified**

| Service type | What it covers |
| --- | --- |
| `hospital` | Sites whose category or name indicates a hospital. Dental services under an independent-hospital heading remain `other`; in Northern Ireland, only independent hospitals with *hospital* in the name are classified as `hospital`. |
| `care home` | Regulated adult care homes, with or without nursing. |
| `gp` | GP practices. |
| `home care` | Office-based care delivered elsewhere: domiciliary care, nurse agencies, supported living, and community-based adult social care. |
| `other` | Clinics, offices and other regulated services in scope. |

**How records are matched across sources**

- **England (ODS + CQC):** A CQC location shares a row with an NHS site
  (`source = ods+cqc`) when its ODS code matches exactly one open ODS site, or
  when its CQC location id matches an open ODS site code under the same parent
  organisation. Where a combined site carries a different CQC provider id from
  its ODS parent, searching either provider finds the site without duplicating
  it. If codes do not match or parent organisations differ, both rows stay
  separate.
- **Wales, Scotland and Northern Ireland:** Registers are not merged across
  sources, so a site listed by two publishers can appear twice.
- **Provider vs health area:** A **provider** link represents the organisation
  recorded as running a site. A **health area** link represents the geographical
  ICB, health board or HSC trust area. GP practices in Northern Ireland and
  Scotland carry health-area links rather than provider links.
"""
)

st.subheader("How the records relate")
_relationship_diagram()
st.markdown(
    """
An organisation is an NHS trust, independent healthcare provider, health board
or registered care provider. A health area is an integrated care board, health
board or HSC trust area. In England, a Care Quality Commission location shares a
row with an NHS site when its organisation code matches one open site, or when
its regulator id matches an open NHS site code under the same parent
organisation.
"""
)

st.header("How current the data is")
st.markdown(currency_markdown(paths))

st.header("Sources and licence")
st.markdown(
    """
| Country | Source | What it covers | Identifying code (`code_system`) |
| --- | --- | --- | --- |
| England | NHS England ODS (`etr`, `ets`, `ephp`, `ephpsite`) | NHS trusts, independent healthcare providers and their sites | ODS code (`ods`) |
| England | Care Quality Commission (CQC) | Active regulated care homes, hospitals, GP practices, home care and clinics | CQC location & provider id (`cqc_location`, `cqc_provider`) |
| Wales | NHS England ODS (`wlhb`, `wlhbsite`, `epraccur`) | Local health boards, board sites and Welsh GP practices | ODS code (`ods`) |
| Wales | Care Inspectorate Wales (CIW) | Regulated adult care homes, domiciliary support and adult placement | CIW service & provider URN (`ciw_service`, `ciw_provider`) |
| Scotland | Public Health Scotland (PHS) | NHS hospitals, GP practices and council-to-health-board lookup | PHS hospital, practice & board code (`phs_hospital`, `phs_practice`, `phs_health_board`) |
| Scotland | Care Inspectorate | Active adult care homes, care at home, housing support, nurse agencies and adult placement | Service & provider number (`care_inspectorate_service`, `care_inspectorate_provider`) |
| Northern Ireland | NHS England ODS (`npraccur`, `niorg`) | Active GP practices and HSC organisations | ODS code (`ods`) |
| Northern Ireland | RQIA | Regulated adult care homes, domiciliary/nursing agencies, independent hospitals/clinics and adult placement | RQIA service id (`rqia_service`; provider key derived from name) |
| Northern Ireland | Checked HSC hospital list | Maintained list of HSC acute and community hospitals | Site key (`hsc_seed`) and HSC trust code (`hsc_trust`) |
| United Kingdom | Office for National Statistics (NSPL) | Postcode-to-geography lookup (country, region, county, local authority, health area) | ONS GSS & postcode codes (`ons_*`) |
"""
)
st.markdown(attribution_markdown(attribution_year(paths.manifest)))
st.markdown("The application code is licensed under the MIT License; source datasets remain under the Open Government Licence v3.0.")

st.header("Columns")
st.markdown(
    """
| Column | Meaning |
| --- | --- |
| `name` | Display name of the site. Combined England records (`ods+cqc`) keep the CQC name. |
| `location_id` | Stable surrogate site key (MD5 hash of the governing source identifier). Import as text. |
| `parent_name` | Name of the organisation recorded as running the site. |
| `parent_code` | Organisation code for `parent_name`. |
| `address` | Street address (excluded from `match_string`). |
| `town` | Town or city. |
| `postcode` | Formatted postcode with standard spacing. |
| `postcode_compact` | Upper-case postcode with spaces removed. |
| `country` | England, Wales, Scotland or Northern Ireland. |
| `local_authority` | Local authority name for the postcode (falls back to CQC for unmatched England postcodes). |
| `local_authority_code` | ONS local authority code. |
| `county` | County name for England postcodes (blank elsewhere and for English unitary authorities). |
| `county_code` | ONS county code (England only). |
| `region` | Region name for England postcodes (blank elsewhere). |
| `region_code` | ONS region code (England only). |
| `health_area` | Integrated care board, health board or HSC trust area name. |
| `health_area_type` | `icb`, `health_board` or `hsc_trust`. |
| `health_area_code` | Identifier for the health area (`ONS` code, Scottish `S08…` board code, or HSC trust code). |
| `health_area_ods_code` | ODS code for the health area where one exists (blank for Scottish boards without an ODS mapping). |
| `nhs_code` | Site code from ODS or Public Health Scotland, where present. |
| `nhs_code_system` | Issuing system for `nhs_code`: `ods`, `phs_hospital` or `phs_practice`. |
| `regulator` | `CQC`, `CIW`, `Care Inspectorate` or `RQIA`, where present. |
| `regulator_id` | Location or service id on that regulator's register. |
| `service_type` | `hospital`, `care home`, `gp`, `home care` or `other`. |
| `source` | Source register (`ods`, `cqc`, `ods+cqc`, `phs`, `ciw`, `care_inspectorate`, `rqia` or `hsc`). |
| `valid_from` | Start or registration date from the source, where published (`YYYY-MM-DD`). |
| `valid_to` | End date (`YYYY-MM-DD`). Blank for current sites. |
| `match_string` | Optional (placed last when selected). Upper-case discovery keywords with punctuation and common words removed. |

The download from this page contains the sites in your selection. For automated
or relational use, download `location-reference-bundle.zip` (schema `1.0.0`)
from the release page: it bundles all five reference tables (`location`,
`search_entity`, `entity_site`, `entity_alias`, `entity_identifier`), release
change logs, a data dictionary, coverage notes, and a SHA-256 manifest.
"""
)

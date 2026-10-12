# Healthcare location reference

Look up UK healthcare locations and copy a keyword string for fuzzy matching.

Search at country, region, county, local authority, integrated care board, provider, or site level. Results list the sites under that place, with names, aliases, parent organisations, postcodes, and organisation codes. Each location includes one pasteable string of keywords and aliases.

## MVP

England, current records:

- NHS Organisation Data Service — trusts and sites
- Care Quality Commission — registered locations, including care homes
- Office for National Statistics postcode geography

## Stack

Python, DuckDB, dbt, and Streamlit.

## Data

Source datasets are used under the Open Government Licence. Attribute NHS England, the Care Quality Commission, and the Office for National Statistics when republishing extracts.

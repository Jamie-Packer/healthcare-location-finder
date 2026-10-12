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

## Run locally

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m ingest.download
.venv\Scripts\python -m ingest.build
.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

`python -m ingest.build --fixtures` builds a tiny sample used to check the models.

## Data

Source datasets are used under the Open Government Licence. Attribute NHS England, the Care Quality Commission, and the Office for National Statistics when republishing extracts.

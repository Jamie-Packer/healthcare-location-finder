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

Use that last command. A global `streamlit` from another environment can be older than 1.48, and this app will not start on it.

`python -m ingest.build --fixtures` builds a tiny sample used to check the models.

## Source files

Downloaded files keep the publisher's names. Those names are report ids.

Organisation Data Service reports:

| File | Contents |
| --- | --- |
| `etr.csv` | NHS trusts |
| `ets.csv` | NHS trust sites |
| `ephp.csv` | Independent sector healthcare providers |
| `ephpsite.csv` | Sites of those providers |
| `eother.csv` | Other NHS organisations, including integrated care boards |

Care Quality Commission active locations are the England register of care homes, hospitals, GP practices, and other registered services. Care homes in the search come from that file. The care-home flag on each row marks them.

Office for National Statistics abbreviations: `CTRY` country, `RGN` region, `CTY` county, `LAD` local authority district, `ICB` integrated care board. `NSPL` is the National Statistics Postcode Lookup.

## Data

Source datasets are used under the Open Government Licence. Attribute NHS England, the Care Quality Commission, and the Office for National Statistics when republishing extracts.

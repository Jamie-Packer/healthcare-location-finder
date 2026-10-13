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
.venv\Scripts\pip install -r requirements-build.txt
.venv\Scripts\python -m ingest.download
.venv\Scripts\python -m ingest.build
.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

`requirements.txt` is the app. `requirements-build.txt` adds the download and dbt tools. Use the project virtual environment for that last command. A global `streamlit` from another environment can be older than 1.48, and this app will not start on it.

`python -m ingest.refresh` downloads the current source files, checks them, builds the marts, and writes `data/mart/manifest.json`. `python -m ingest.build --fixtures` builds a tiny sample used to check the models.

Without a local build, the app uses the [location data release](https://github.com/Jamie-Packer/healthcare-location-finder/releases/tag/data-latest). If that release cannot be downloaded, it opens the small sample in `data/sample/`.

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

## Refresh

A GitHub Actions workflow checks the sources every Monday at 04:00 UTC (04:00 GMT, or 05:00 during British Summer Time). When the files have changed and the row counts stay inside the usual band, it replaces the `data-latest` release. A failed check keeps the previous release and opens an issue. Run the workflow by hand with "force" to publish a deliberate larger change.

The built parquet files are not stored in git. GitHub pauses a scheduled workflow after 60 days without repository activity, such as a commit, issue, or pull request. The workflow updates the release notes on every check.

## Deploy

Streamlit Community Cloud can run `app/streamlit_app.py` from this repository with `requirements.txt` and Python 3.12. The app reads the `data-latest` release, so publish that release once before sharing the app.

## Data

Source datasets are used under the [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Attribute NHS England, the Care Quality Commission, and the Office for National Statistics when republishing extracts.

Contains OS data © Crown copyright and database right. Contains Royal Mail data © Royal Mail copyright and database right. Contains National Statistics data © Crown copyright and database right. See the [ONS geography licences](https://www.ons.gov.uk/methodology/geography/licences).

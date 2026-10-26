# Healthcare location reference

Look up UK healthcare locations and download a table of the sites you select.

Search for a country, region, county, local authority, integrated care board, health board, HSC trust area, provider or single site. The app lists the current sites under that place, and you can narrow them by service type and country. The download has one row per site with the columns you choose. By default that is the name, parent, town, postcode, country, local authority, health area and service type.

## Coverage

Current records for:

- **England:** NHS Organisation Data Service trusts and sites, and every location registered with the Care Quality Commission, including care homes.
- **Wales:** NHS health boards and their sites, GP practices, and adult services registered with Care Inspectorate Wales.
- **Scotland:** Public Health Scotland hospitals and GP practices, and adult services registered with the Care Inspectorate.
- **Northern Ireland:** GP practices, adult services registered with RQIA, and a checked list of HSC hospitals.

Every site gets its local authority and health area from the Office for National Statistics postcode lookup. The health area is an integrated care board in England, a health board in Wales and Scotland, and an HSC trust area in Northern Ireland. Region and county are filled for England only.

Not covered yet: independent hospitals and clinics registered with Healthcare Inspectorate Wales or Healthcare Improvement Scotland, the Northern Ireland community estate, and Welsh branch surgeries. The Northern Ireland hospital list is not a live feed. The build checks it against the postcode lookup and the trust list.

## Stack

Python, DuckDB, dbt and Streamlit.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements-build.txt
.venv\Scripts\python -m ingest.download
.venv\Scripts\python -m ingest.build
.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

`requirements.txt` is the app. `requirements-build.txt` adds the download and dbt tools. Start the app with the project's own Python, because a global `streamlit` older than 1.48 will not run it.

Other commands:

- `python -m ingest.refresh` downloads the current source files, checks them, builds the marts and writes `data/mart/manifest.json`.
- `python -m ingest.build --fixtures` builds a tiny test project used to check the models.
- `python -m pytest` runs the tests.

Without a local build, the app downloads the [location data release](https://github.com/Jamie-Packer/healthcare-location-finder/releases/tag/data-latest). If that fails, it opens the small sample in `data/sample/`.

## Source files

Downloaded files keep the publisher's names, which are report ids.

Organisation Data Service reports:

| File | Contents |
| --- | --- |
| `etr.csv` | NHS trusts |
| `ets.csv` | NHS trust sites |
| `ephp.csv` | Independent sector healthcare providers |
| `ephpsite.csv` | Sites of those providers |
| `eother.csv` | Other NHS organisations, including integrated care boards |
| `wlhb.csv` | Welsh health boards |
| `wlhbsite.csv` | Sites of those boards |
| `epraccur.csv` | GP practices. The build keeps the Welsh rows |
| `niorg.csv` | Northern Ireland organisations, used for the trust list |
| `npraccur.csv` | Northern Ireland GP practices |

The Care Quality Commission active-locations file is the England register of care homes, hospitals, GP practices and other registered services.

Care Inspectorate Wales, the Care Inspectorate and RQIA add adult social care in Wales, Scotland and Northern Ireland. Columns that name people are dropped when those files are converted. Children's services, fostering, adoption and adult day care are left out.

Public Health Scotland publishes the Scottish hospital list, the GP practice list and the lookup from council area to NHS board.

Office for National Statistics abbreviations: `CTRY` country, `RGN` region, `CTY` county, `LAD` local authority district, `ICB` integrated care board, `SICBL` sub-integrated care board location. `NSPL` is the National Statistics Postcode Lookup. The Welsh health board and the Northern Ireland commissioning area come from its sub-integrated care board column.

## Refresh

A GitHub Actions workflow checks the sources every Monday at 04:00 UTC (04:00 GMT, or 05:00 during British Summer Time). When a source has changed and the row counts stay inside the usual range, it replaces the `data-latest` release. Each release also stores `source-cache.zip`, the last good copy of every source.

If one source fails, the refresh reuses its last good copy, marks it stale, and still publishes the sources that worked. The workflow run then fails and opens an issue naming the source. If a required England source has no saved copy, nothing is published and the previous release stays.

The first build after a new country is added needs a manual run with "force" ticked, because the new rows fall outside the usual range.

Built parquet files are not stored in git. GitHub pauses a scheduled workflow after 60 days without repository activity, such as a commit, issue or pull request. The workflow updates the release notes on every check.

## Deploy

Streamlit Community Cloud can run `app/streamlit_app.py` from this repository with `requirements.txt` and Python 3.12. The app reads the `data-latest` release without a token, so the repository must be public and the release must exist before you share the app. To create it, run the "Refresh location data" workflow once with "force" ticked. If the download fails, the app shows the bundled sample with a warning and tries again on the next page load.

The theme lives in `.streamlit/config.toml`, with fonts loaded in `app/theme.py`.

## Data

Source datasets are used under the [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Attribute NHS England, the Care Quality Commission, Care Inspectorate Wales, Public Health Scotland, the Care Inspectorate, RQIA and the Office for National Statistics when you republish extracts.

Contains OS data © Crown copyright and database right. Contains Royal Mail data © Royal Mail copyright and database right. Contains National Statistics data © Crown copyright and database right. See the [ONS geography licences](https://www.ons.gov.uk/methodology/geography/licences).

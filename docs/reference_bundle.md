# Location reference bundle

Schema `1.0.0`. Column definitions, joins, identifier recipes and name normalisation are in [data_dictionary.md](data_dictionary.md). This note is how to download, check, load and replace one build.

A build id identifies one produced dataset. A new build time does not by itself mean the rows changed. Adding a column is compatible within major version 1. Renaming, removing, or changing the meaning of a column needs a new major version. Do not import a bundle whose `schema_version` is missing or whose major version is not 1.

## Download

The refresh workflow copies the current files onto the `data-latest` release. Until the first publish of schema 1.0.0, that release does not contain the zip. After that publish, the files are:

- <https://github.com/Jamie-Packer/healthcare-location-finder/releases/download/data-latest/location-reference-bundle.zip>
- <https://github.com/Jamie-Packer/healthcare-location-finder/releases/download/data-latest/location-reference-bundle.zip.sha256>

The zip is one build. It contains `location.csv`, `search_entity.csv`, `entity_site.csv`, `entity_alias.csv`, `entity_identifier.csv`, `identity_changes.csv`, `entity_changes.csv`, `manifest.json`, `data_dictionary.md`, `coverage.md`, `ATTRIBUTION.md` and `release_diff.json`. The `.sha256` file is the checksum of the zip and is not inside it.

Each publish also creates a release named `data-<build_id>`. That tag is not replaced. A later `data-latest` does not change a tag you have already downloaded. The release this contract replaces had no build id, so keep your own copy of any older snapshot.

The Parquet files on the same release are the same rows in another format. They are not inside the zip. `manifest.json` lists them under `parquet`. The files inside the zip are listed under `outputs`.

`build_status` in the manifest is `normal` when every source was fetched, `degraded` when a source was reused from its last good copy, and `partial` when a source was left out. `sample` and `fixture` are not full snapshots. Do not use them when the download fails.

## Check

1. Compare the zip's SHA-256 with the `.sha256` file. On Windows, `Get-FileHash location-reference-bundle.zip -Algorithm SHA256`. The two hashes must match before you unzip.
2. Unzip the whole archive into an empty folder. One zip is one build. Do not mix files from two zips.
3. Open `manifest.json`. `schema_version` must start with `1.`. `worktree_dirty` is false on a release built from a clean checkout. `outputs` gives each file's row count, byte size and SHA-256.
4. Read `coverage.md` for the geography, the exclusions, and whether any source is stale or missing. `publisher_date` is the publisher's edition, `checked_at` is when the file was read, and `built_at` is when the tables were made.

From a checkout of this repository, `python -m ingest.bundle verify location-reference-bundle.zip` checks the manifest, the checksums, the keys, the references and the column types. A schema major version other than 1 fails with `unsupported schema version`. A bad checksum, a duplicate key, a dangling membership or a value that does not match its type fails the same way. A shared alias is allowed.

## Load

Import keys and codes as text, including leading zeros. Empty fields are null. Dates are `YYYY-MM-DD`. Booleans are `true` or `false`. Details are in the dictionary.

Load `manifest.json` and `data_dictionary.md` first and stop if the schema major version is not 1. Then load the five reference tables, in any order:

1. `location.csv`
2. `search_entity.csv`
3. `entity_site.csv`
4. `entity_alias.csv`
5. `entity_identifier.csv`

`identity_changes.csv` and `entity_changes.csv` are the comparison with the previous release. They are not part of the reference model.

Joins:

1. `search_entity.entity_id` to `entity_site.entity_id`.
2. `entity_site.location_id` to `location.location_id`.
3. `entity_alias.entity_id` and `entity_identifier.entity_id` to `search_entity.entity_id`.
4. A site entity joins to its site on `search_entity.location_id`. That column is empty for every other entity type. `entity_id` for a site is `site:` plus the location id, so the two values are not the same.

Replace the folder below with the directory you extracted. It does not have to be this path.

```powerquery
let
    LocationReferenceFolder = "C:\location-reference",
    LoadText = (fileName as text, textColumns as list) as table =>
        let
            source = Csv.Document(
                File.Contents(LocationReferenceFolder & "\" & fileName),
                [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
            ),
            promoted = Table.PromoteHeaders(source, [PromoteAllScalars = true]),
            typed = Table.TransformColumnTypes(
                promoted,
                List.Transform(textColumns, each {_, type text})
            )
        in
            typed,
    Location = LoadText("location.csv", {"location_id", "nhs_code", "regulator_id", "parent_code", "postcode"}),
    Entity = LoadText("search_entity.csv", {"entity_id", "code", "location_id"}),
    Membership = LoadText("entity_site.csv", {"entity_id", "location_id"}),
    Alias = LoadText("entity_alias.csv", {"alias_id", "entity_id", "source_record_key"}),
    Identifier = LoadText("entity_identifier.csv", {"entity_id", "identifier_value"})
in
    Location
```

Give the same text type to every other key or code you keep. Filter `Membership` to one `entity_id`, then join `Location` on `location_id`, for the current sites linked to that place.

## Examples

These rows show the joins. A later build can add or drop a row. The zip you downloaded is the list for that build.

**Site.** The Shelburne Hospital, `location_id` `92c342221e225e893ef81b724be65cbe`. NHS code `NT435` (`nhs_code_system` `ods`) and Care Quality Commission id `1-128767252`. `location_id_basis` is `ods` because that NHS code is on one current location. The identifier table keeps both values. The site entity is `site:` plus the location id, and `search_entity.location_id` carries the location id itself.

**Provider.** `provider:RYY`, Kent Community Health NHS Foundation Trust, subtype `nhs_trust` from `ods_etr`. The provider link does not say which county a site is in. In one build this trust had sites in Kent, East Sussex and Surrey. Selecting the provider returns all of those sites. Selecting the county `county:E10000016` (Kent) returns the Kent sites of every provider, not this trust alone.

**Area.** Medway is a unitary authority. Its sites have no `county_name`, so they are not members of Kent. That is the same rule as the Medway check in the model tests. A missing county outside England, and for an English unitary authority, is unknown rather than an error.

**Same name, two sites.** Airedale General Hospital, postcode `BD20 6TD`, is two sites:

| location_id | Provider | Regulator id |
| --- | --- | --- |
| `2fafc5aa0cd448efe23f0e106a5e6725` | Airedale NHS Foundation Trust (`RCF`) | `RCF22` |
| `cfcbb68d1f4fdb699add27f72def305a` | Bradford District Care NHS Foundation Trust (`TAD`) | `TADY6` |

The shared name does not merge them. Compare names on `entity_alias`, not on `match_string`. `match_string` also contains the parent, the town, the postcode and the codes, and it drops common words.

## Identifiers

`location_id` and `entity_id` are text. They are not replaced on a rebuild when the governing source value is unchanged. A change of name, spelling, address or row order does not change them. A name match is not a merge.

Northern Ireland hospital ids hash the stored `site_key`. That key was first written from the upper-case name and the compacted postcode, and it is now a column on the hospital list. Editing the name or the postcode does not mint a new id. Editing `site_key` does. RQIA provider ids are derived from the provider name, because that register has no provider id. A renamed RQIA provider is a new provider key. No other id is minted from a display name.

An England location moves from a Care Quality Commission id to an Organisation Data Service id when its organisation code is on exactly one current location. The old and new keys are both kept in `entity_identifier`. That is a transition. It is not a promise that the surrogate never changes.

`identity_changes.csv` is the difference from the previous `data-latest` release. `transition` is one row with both site keys, including a Care Quality Commission location that moved to an Organisation Data Service key. `unresolved` means the same identifier points at more than one site, and this build does not pick one: each of those sites is its own row, with only that release's key filled in. A site whose key changed is not also listed as removed and added. `entity_changes.csv` lists added, removed and renamed sites and entities, and added or removed memberships. A rename keeps the same id. Nothing in either file deletes a previous zip.

## Replace a snapshot

1. Keep the zip you are using, and the `.sha256` file beside it.
2. Download the new zip and its `.sha256` file. The build id is in `manifest.json` after you unzip, and it is also the name of the `data-<build_id>` release.
3. Check the new checksum, then unzip into a new folder. Point the folder parameter at that folder.
4. To go back, point the folder parameter at the previous extract. Do not copy single CSV files from a newer zip into an older folder.

The Monday workflow publishes when the source files change, and also when the output contract changes and the files do not. A failed check does not replace `data-latest` or an existing `data-<build_id>` release.

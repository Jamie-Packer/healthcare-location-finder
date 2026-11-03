# Location reference data dictionary

Schema version `1.0.0`. Name normalisation `name-norm-1`.

A schema version describes this interface. A build id identifies one produced dataset. A new build time does not by itself mean the rows changed. Adding a column is compatible within the same major version. Renaming, removing, or changing the meaning of a column needs a new major version.

Empty fields are null. Dates are ISO `YYYY-MM-DD`. Timestamps are UTC. Identifiers and codes are text. Booleans are `true` or `false`.

## Joins

1. `search_entity.entity_id` to `entity_site.entity_id`.
2. `entity_site.location_id` to `location.location_id`.
3. `entity_alias.entity_id` and `entity_identifier.entity_id` to `search_entity.entity_id`.
4. A site entity joins to its site with `search_entity.location_id`. That column is empty for every other entity type. `entity_id` is `site:` plus the location id, so the two values are not the same.

A country, county, provider, or other entity returns the current sites linked to it. That is not a certified population of every healthcare setting in the area. A provider can cover more than one county. A site's county does not say which provider runs it.

## How display names are chosen

Provider names prefer the organisation's own register. If the Care Quality Commission records the same name apart from case, the Care Quality Commission casing is kept. Otherwise the name that appears on the most sites is used, and the lowest name breaks a tie. The same rule, most frequent then lowest, chooses any other entity whose source rows disagree. A case-only difference is kept as its own alias so the original text remains available.

## Name normalisation

`name-norm-1` upper-cases the text, strips accents, turns `&` into `AND`, drops apostrophes, and turns every other run of punctuation or spacing into a single space. It does not remove words. `match_string` is a separate discovery field: it also removes common words and mixes in the parent, town, postcode and codes. Compare names with `entity_alias`, not with `match_string`.

A value that normalisation reduces to nothing is kept, with `normalisation_status` `empty_after_normalisation` and an empty `alias_normalised`. The same normalised name may belong to several entities.

## Identifiers

`location_id` is `md5` of a prefix and the governing source value:

| Basis | Input |
| --- | --- |
| `ods` | `ods:` and the Organisation Data Service site code |
| `cqc` | `cqc:` and the Care Quality Commission location id |
| `phs` | `phs:` and the Public Health Scotland hospital or practice code |
| `ciw` | `ciw:` and the Care Inspectorate Wales service URN |
| `care_inspectorate` | `care_inspectorate:` and the Care Inspectorate service id |
| `rqia` | `rqia:` and the RQIA service id |
| `hsc_seed` | `hsc:` and the manually maintained `site_key` on the Northern Ireland hospital list |

An England Care Quality Commission location uses the Organisation Data Service basis when its organisation code appears on exactly one current Care Quality Commission location. A later change in that count changes `location_id`. The identifier table keeps both codes. That change is a transition, not a guarantee that the surrogate stayed put.

A provider key is `provider:` plus the organisation code. The `provider:` prefix is the entity type. The issuing system is `identifier_system`. Organisation Data Service codes and Care Quality Commission provider ids of the form `1-…` stay distinct. Where the Care Quality Commission uses an Organisation Data Service organisation code, the published system is `ods`.

Northern Ireland hospital keys are manually maintained. `site_key` was first written from the upper-case name and the postcode with the space removed, and that text is now stored on the hospital list. Changing the name or postcode columns does not change `location_id`. Changing `site_key` does, and the new value is a different site. RQIA provider keys are `derived`: the register has no provider id, so the key is an md5 of the provider name. A name change mints a new provider key. No other identifier is minted from a display name.

Entity ids are not replaced on a rebuild when the governing source value is unchanged. A change of name, spelling, address, or row order does not change them.

## Membership

| membership_type | Meaning |
| --- | --- |
| `self` | The site entity for that site. |
| `provider` | The organisation recorded as running the site. |
| `postcode` | The site's own postcode. |
| `geography` | Country, region, county, or local authority from the postcode lookup, or the country recorded on the source when the postcode is not in the lookup. |
| `health_area` | Integrated care board, health board, or HSC trust area. |

These are current reference links. A missing county is normal outside England, and for English unitary authorities. Health boards, integrated care boards and HSC trust areas are different entity types.

NHS trusts, Welsh health boards, Scottish health boards and HSC trusts are included even when they have no current site (`site_count` 0). Independent providers are included only when a current site records them. Provider subtype comes from the organisation register or, failing that, from one Care Quality Commission sector or one Care Inspectorate Wales provider type. It is `unknown`, and `entity_subtype_source` is empty, when those sources do not agree or do not classify the organisation. It is never guessed from the name.

## Code lists

Identifier systems: `ods`, `phs_hospital`, `phs_practice`, `phs_health_board`, `cqc_location`, `cqc_provider`, `ciw_service`, `ciw_provider`, `care_inspectorate_service`, `care_inspectorate_provider`, `rqia_service`, `rqia_provider`, `hsc_seed`, `hsc_trust`, `ons_region`, `ons_county`, `ons_local_authority`, `ons_health_area`, `ons_postcode`, `ods_health_area`, `unknown`.

Provider subtypes: `nhs_trust`, `nhs_health_board`, `hsc_trust`, `independent_healthcare`, `nhs_organisation`, `social_care`, `primary_medical`, `dental`, `ambulance`, `local_authority`, `charity`, `company`, `individual`, `unknown`.

`nhs_code` on a site is not one system. Use `nhs_code_system`. `unknown` means a provider code is published but the source does not say which organisation issued it. The same text under `ods` or `cqc_provider` is a different identifier.

## Tables

### `location.csv`

One current reference site. Key: `location_id`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `location_id` | text | no | Surrogate site key. An md5 of the governing source identifier. Import as text. |
| `name` | text | no | Display name. A combined England record keeps the Care Quality Commission name. |
| `parent_name` | text | yes | Organisation name recorded on the site row. |
| `parent_code` | text | yes | Organisation code recorded on the site row. The issuing system is on the provider entity, not in this column. |
| `address` | text | yes | Street address. It is not part of match_string. |
| `postcode` | text | yes | Postcode, with the usual space. |
| `postcode_compact` | text | yes | Postcode with spaces removed. |
| `town` | text | yes | Town or city. |
| `local_authority_name` | text | yes | Local authority name for the postcode. |
| `local_authority_code` | text | yes | ONS local authority code. |
| `county_name` | text | yes | County name. Filled for England. |
| `county_code` | text | yes | ONS county code. Filled for England. |
| `region_name` | text | yes | Region name. Filled for England. |
| `region_code` | text | yes | ONS region code. Filled for England. |
| `health_area_name` | text | yes | Integrated care board, health board, or HSC trust area. |
| `health_area_code` | text | yes | Code that identifies the health area in entity_id. |
| `health_area_ods_code` | text | yes | Organisation Data Service code for the health area, when there is one. |
| `health_area_type` | text | yes | icb, health_board, or hsc_trust. |
| `country_name` | text | yes | England, Wales, Scotland, or Northern Ireland. |
| `nhs_code` | text | yes | Site code from the Organisation Data Service or Public Health Scotland. See nhs_code_system. |
| `regulator` | text | yes | Care Quality Commission, CIW, Care Inspectorate, or RQIA. |
| `regulator_id` | text | yes | Location id on that register. |
| `service_type` | text | yes | hospital, care home, gp, home care, or other. |
| `source` | text | yes | Register the row came from. ods+cqc means the England records were combined. |
| `valid_from` | date | yes | Start date from the source, where the publisher gives one. |
| `valid_to` | date | yes | End date. Current sites are open, so this is empty. |
| `nhs_code_system` | text | yes | ods, phs_hospital, or phs_practice. Empty when nhs_code is empty. |
| `regulator_id_system` | text | yes | cqc_location, ciw_service, care_inspectorate_service, or rqia_service. |
| `location_id_basis` | text | no | Namespace hashed into location_id: ods, cqc, phs, ciw, care_inspectorate, rqia, or hsc_seed. |
| `health_area_source` | text | yes | source_record, ons_postcode, or ods_icb_code. |
| `match_string` | text | no | Upper-case keywords for discovery. Names, parent, town, postcode and codes, with punctuation and common words removed. |

### `search_entity.csv`

One selectable place: a country, region, county, local authority, health area, postcode, provider, or site. Key: `entity_id`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `entity_id` | text | no | Stable entity key. Site keys are site: followed by location_id, not the location_id alone. |
| `entity_type` | text | no | country, region, county, local_authority, icb, health_board, hsc_trust, postcode, provider, or site. |
| `name` | text | no | Display name. Where source rows disagree, the most frequent name is used and the lowest name breaks a tie. |
| `code` | text | yes | Code shown for the entity. A health area prefers the Organisation Data Service code when it has one. |
| `code_system` | text | yes | Issuing system of code. Empty for a country, which has no code. |
| `search_text` | text | yes | Upper-case text used by the location search. |
| `entity_subtype` | text | yes | Provider classification. Empty when the entity is not a provider. unknown when it is a provider and the source does not classify it. |
| `entity_subtype_source` | text | yes | Reference that supplied the subtype. Empty when the entity is not a provider, or when the subtype is unknown. |
| `location_id` | text | yes | Set only for a site entity. This is the join to location. It is not equal to entity_id. |
| `site_count` | integer | no | Current sites linked to the entity. Zero means an NHS organisation with no current site. |

### `entity_site.csv`

One current link between an entity and a site. Key: `entity_id`, `location_id`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `entity_id` | text | no | Entity key. |
| `location_id` | text | no | Site key. |
| `membership_type` | text | no | self, provider, postcode, geography, or health_area. |
| `membership_source` | text | no | Provider links use the site source: ods, ods+cqc, cqc, phs, ciw, care_inspectorate, rqia, or hsc. Other links use ons_postcode, country_fallback, source_record, ods_icb_code, site_record, or location. |

### `entity_alias.csv`

One name for one entity from one source. Key: `alias_id`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `alias_id` | text | no | md5 of entity_id, alias_type, source and the original text. |
| `entity_id` | text | no | Entity key. |
| `alias_text` | text | no | Name as recorded. Commas, quotes and line breaks are preserved. |
| `alias_normalised` | text | yes | name-norm-1 form. Empty when normalisation removes the whole value. |
| `alias_type` | text | no | preferred, alternative, ods_name, brand, known_as, or address_name. |
| `is_preferred` | boolean | no | True for the one display name of the entity. |
| `source` | text | no | Register or reference that supplied this text. |
| `source_record_key` | text | yes | Source record key when the register has one. |
| `normalisation_status` | text | no | ok, or empty_after_normalisation. |

### `entity_identifier.csv`

One source identifier for one entity. Key: `entity_id`, `identifier_system`, `identifier_value`, `source`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `entity_id` | text | no | Entity key. |
| `identifier_system` | text | no | Issuing system. See the identifier systems list. |
| `identifier_value` | text | no | Value as text, including any leading zeros. |
| `identifier_origin` | text | no | source_assigned, manually_maintained, or derived. |
| `identifier_role` | text | no | primary when this value governs the entity key, otherwise additional. |
| `source` | text | no | Register or reference this value was taken from. |

### `identity_changes.csv`

One identifier and one site it points at, where the site key changed or the identifier is ambiguous. Key: `change`, `identifier_system`, `identifier_value`, `previous_location_id`, `location_id`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `change` | text | no | transition when both site keys are filled. unresolved when the identifier points at more than one site; each of those sites is its own row and only one site key is filled. |
| `identifier_system` | text | no | Comparable identifier system. |
| `identifier_value` | text | no | Identifier value. |
| `previous_location_id` | text | yes | Site key in the previous release. Empty when this unresolved row is a site only in this release. |
| `location_id` | text | yes | Site key in this release. Empty when this unresolved row is a site only in the previous release. |

### `entity_changes.csv`

One added, removed, or renamed site or entity, or one added or removed membership. A site whose key changed is a transition in identity_changes, not an added site and a removed site. Key: `record_type`, `change`, `record_id`.

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `record_type` | text | no | site, entity, or membership. |
| `change` | text | no | added, removed, or renamed. |
| `record_id` | text | no | location_id, entity_id, or entity_id and location_id joined with a vertical bar. |
| `previous_value` | text | yes | Previous display name, for a rename. |
| `current_value` | text | yes | Current display name, for a rename. |

## Build manifest

`manifest.json` describes one build. `schema_version` is this interface. `contract_sha256` hashes the output filenames, keys and columns, so a shape change is visible even when the schema version is unchanged. `build_id` identifies one produced dataset and starts with the UTC build time. `built_at` is when the tables were produced. `commit` is the git commit. `worktree_dirty` is true when that commit had uncommitted changes; a release built from a clean checkout is false. `data_scope` is `current`. `build_status` is `normal`, `degraded`, `partial`, `sample` or `fixture`. `data_fingerprint` hashes the five reference CSV checksums, so a new build time with the same fingerprint means those rows did not change.

`outputs` lists the files inside the zip. Each table entry has its filename, row count, byte size, SHA-256, grain, keys, ordered `columns` (`name`, `type`, `nullable`) and a `nulls` count per column. An empty value is unknown. A column this contract does not list is not in the file. `parquet` lists the Parquet files published beside the zip. Those files are not inside the zip.

The column definitions in the zip are `data_dictionary.md`.

## CSV

UTF-8 without a byte order mark. Comma separator. Fields that contain a comma, quote, or line break are wrapped in double quotes, and a quote inside a field is doubled. Line endings are line feeds. An empty field is null. Dates are `YYYY-MM-DD`. Rows are sorted by the key columns.

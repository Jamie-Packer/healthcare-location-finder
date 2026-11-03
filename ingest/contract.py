"""Public column contract for the reference bundle.

schema_version describes this interface. A build_id identifies one produced
dataset. Adding a nullable column is a compatible change. Renaming, removing,
or redefining a column needs a new major version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

SCHEMA_VERSION = "1.0.0"
SUPPORTED_MAJOR = 1
NORMALISATION_VERSION = "name-norm-1"
BUNDLE_ZIP = "location-reference-bundle.zip"
BUNDLE_SHA = "location-reference-bundle.zip.sha256"


@dataclass(frozen=True)
class Column:
    name: str
    logical_type: str
    nullable: bool
    description: str


@dataclass(frozen=True)
class Table:
    name: str
    filename: str
    parquet: str | None
    grain: str
    keys: tuple[str, ...]
    columns: tuple[Column, ...]


def _text(name: str, description: str, nullable: bool = True) -> Column:
    return Column(name, "text", nullable, description)


def _date(name: str, description: str) -> Column:
    return Column(name, "date", True, description)


def schema_major(version: str) -> int | None:
    head = str(version).split(".", 1)[0]
    return int(head) if head.isdigit() else None


def supported_schema(version: str) -> bool:
    return schema_major(version) == SUPPORTED_MAJOR


LOCATION = Table(
    name="location",
    filename="location.csv",
    parquet="location.parquet",
    grain="One current reference site.",
    keys=("location_id",),
    columns=(
        _text("location_id", "Surrogate site key. An md5 of the governing source identifier. Import as text.", False),
        _text("name", "Display name. A combined England record keeps the Care Quality Commission name.", False),
        _text("parent_name", "Organisation name recorded on the site row."),
        _text("parent_code", "Organisation code recorded on the site row. The issuing system is on the provider entity, not in this column."),
        _text("address", "Street address. It is not part of match_string."),
        _text("postcode", "Postcode, with the usual space."),
        _text("postcode_compact", "Postcode with spaces removed."),
        _text("town", "Town or city."),
        _text("local_authority_name", "Local authority name for the postcode."),
        _text("local_authority_code", "ONS local authority code."),
        _text("county_name", "County name. Filled for England."),
        _text("county_code", "ONS county code. Filled for England."),
        _text("region_name", "Region name. Filled for England."),
        _text("region_code", "ONS region code. Filled for England."),
        _text("health_area_name", "Integrated care board, health board, or HSC trust area."),
        _text("health_area_code", "Code that identifies the health area in entity_id."),
        _text("health_area_ods_code", "Organisation Data Service code for the health area, when there is one."),
        _text("health_area_type", "icb, health_board, or hsc_trust."),
        _text("country_name", "England, Wales, Scotland, or Northern Ireland."),
        _text("nhs_code", "Site code from the Organisation Data Service or Public Health Scotland. See nhs_code_system."),
        _text("regulator", "Care Quality Commission, CIW, Care Inspectorate, or RQIA."),
        _text("regulator_id", "Location id on that register."),
        _text("service_type", "hospital, care home, gp, home care, or other."),
        _text("source", "Register the row came from. ods+cqc means the England records were combined."),
        _date("valid_from", "Start date from the source, where the publisher gives one."),
        _date("valid_to", "End date. Current sites are open, so this is empty."),
        _text("nhs_code_system", "ods, phs_hospital, or phs_practice. Empty when nhs_code is empty."),
        _text("regulator_id_system", "cqc_location, ciw_service, care_inspectorate_service, or rqia_service."),
        _text("location_id_basis", "Namespace hashed into location_id: ods, cqc, phs, ciw, care_inspectorate, rqia, or hsc_seed.", False),
        _text("health_area_source", "source_record, ons_postcode, or ods_icb_code."),
        _text("match_string", "Upper-case keywords for discovery. Names, parent, town, postcode and codes, with punctuation and common words removed.", False),
    ),
)

SEARCH_ENTITY = Table(
    name="search_entity",
    filename="search_entity.csv",
    parquet="search_entity.parquet",
    grain="One selectable place: a country, region, county, local authority, health area, postcode, provider, or site.",
    keys=("entity_id",),
    columns=(
        _text("entity_id", "Stable entity key. Site keys are site: followed by location_id, not the location_id alone.", False),
        _text("entity_type", "country, region, county, local_authority, icb, health_board, hsc_trust, postcode, provider, or site.", False),
        _text("name", "Display name. Where source rows disagree, the most frequent name is used and the lowest name breaks a tie.", False),
        _text("code", "Code shown for the entity. A health area prefers the Organisation Data Service code when it has one."),
        _text("code_system", "Issuing system of code. Empty for a country, which has no code."),
        _text("search_text", "Upper-case text used by the location search."),
        _text("entity_subtype", "Provider classification. Empty when the entity is not a provider. unknown when it is a provider and the source does not classify it."),
        _text("entity_subtype_source", "Reference that supplied the subtype. Empty when the entity is not a provider, or when the subtype is unknown."),
        _text("location_id", "Set only for a site entity. This is the join to location. It is not equal to entity_id."),
        Column("site_count", "integer", False, "Current sites linked to the entity. Zero means an NHS organisation with no current site."),
    ),
)

ENTITY_SITE = Table(
    name="entity_site",
    filename="entity_site.csv",
    parquet="entity_site.parquet",
    grain="One current link between an entity and a site.",
    keys=("entity_id", "location_id"),
    columns=(
        _text("entity_id", "Entity key.", False),
        _text("location_id", "Site key.", False),
        _text("membership_type", "self, provider, postcode, geography, or health_area.", False),
        _text(
            "membership_source",
            "Provider links use the site source: ods, ods+cqc, cqc, phs, ciw, care_inspectorate, rqia, or hsc. Other links use ons_postcode, country_fallback, source_record, ods_icb_code, site_record, or location.",
            False,
        ),
    ),
)

ENTITY_ALIAS = Table(
    name="entity_alias",
    filename="entity_alias.csv",
    parquet="entity_alias.parquet",
    grain="One name for one entity from one source.",
    keys=("alias_id",),
    columns=(
        _text("alias_id", "md5 of entity_id, alias_type, source and the original text.", False),
        _text("entity_id", "Entity key.", False),
        _text("alias_text", "Name as recorded. Commas, quotes and line breaks are preserved.", False),
        _text("alias_normalised", "name-norm-1 form. Empty when normalisation removes the whole value."),
        _text("alias_type", "preferred, alternative, ods_name, brand, known_as, or address_name.", False),
        Column("is_preferred", "boolean", False, "True for the one display name of the entity."),
        _text("source", "Register or reference that supplied this text.", False),
        _text("source_record_key", "Source record key when the register has one."),
        _text("normalisation_status", "ok, or empty_after_normalisation.", False),
    ),
)

ENTITY_IDENTIFIER = Table(
    name="entity_identifier",
    filename="entity_identifier.csv",
    parquet="entity_identifier.parquet",
    grain="One source identifier for one entity.",
    keys=("entity_id", "identifier_system", "identifier_value", "source"),
    columns=(
        _text("entity_id", "Entity key.", False),
        _text("identifier_system", "Issuing system. See the identifier systems list.", False),
        _text("identifier_value", "Value as text, including any leading zeros.", False),
        _text("identifier_origin", "source_assigned, manually_maintained, or derived.", False),
        _text("identifier_role", "primary when this value governs the entity key, otherwise additional.", False),
        _text("source", "Register or reference this value was taken from.", False),
    ),
)

IDENTITY_CHANGES = Table(
    name="identity_changes",
    filename="identity_changes.csv",
    parquet=None,
    grain="One identifier and one site it points at, where the site key changed or the identifier is ambiguous.",
    keys=("change", "identifier_system", "identifier_value", "previous_location_id", "location_id"),
    columns=(
        _text("change", "transition when both site keys are filled. unresolved when the identifier points at more than one site; each of those sites is its own row and only one site key is filled.", False),
        _text("identifier_system", "Comparable identifier system.", False),
        _text("identifier_value", "Identifier value.", False),
        _text("previous_location_id", "Site key in the previous release. Empty when this unresolved row is a site only in this release."),
        _text("location_id", "Site key in this release. Empty when this unresolved row is a site only in the previous release."),
    ),
)

ENTITY_CHANGES = Table(
    name="entity_changes",
    filename="entity_changes.csv",
    parquet=None,
    grain="One added, removed, or renamed site or entity, or one added or removed membership. A site whose key changed is a transition in identity_changes, not an added site and a removed site.",
    keys=("record_type", "change", "record_id"),
    columns=(
        _text("record_type", "site, entity, or membership.", False),
        _text("change", "added, removed, or renamed.", False),
        _text("record_id", "location_id, entity_id, or entity_id and location_id joined with a vertical bar.", False),
        _text("previous_value", "Previous display name, for a rename."),
        _text("current_value", "Current display name, for a rename."),
    ),
)

TABLES: tuple[Table, ...] = (
    LOCATION,
    SEARCH_ENTITY,
    ENTITY_SITE,
    ENTITY_ALIAS,
    ENTITY_IDENTIFIER,
    IDENTITY_CHANGES,
    ENTITY_CHANGES,
)

REFERENCE_TABLES: tuple[Table, ...] = TABLES[:5]
PARQUET_TABLES: tuple[Table, ...] = tuple(table for table in TABLES if table.parquet)


def contract_sha256() -> str:
    """Hash of the published filenames, keys and columns.

    A refresh rebuilds when this differs from the previous release, even if
    every source file is unchanged.
    """
    payload = [
        {
            "filename": table.filename,
            "keys": list(table.keys),
            "columns": [
                [column.name, column.logical_type, column.nullable]
                for column in table.columns
            ],
        }
        for table in TABLES
    ]
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

BUNDLE_FILES: tuple[str, ...] = (
    *(table.filename for table in TABLES),
    "manifest.json",
    "data_dictionary.md",
    "coverage.md",
    "ATTRIBUTION.md",
    "release_diff.json",
)

IDENTIFIER_SYSTEMS: tuple[str, ...] = (
    "ods",
    "phs_hospital",
    "phs_practice",
    "phs_health_board",
    "cqc_location",
    "cqc_provider",
    "ciw_service",
    "ciw_provider",
    "care_inspectorate_service",
    "care_inspectorate_provider",
    "rqia_service",
    "rqia_provider",
    "hsc_seed",
    "hsc_trust",
    "ons_region",
    "ons_county",
    "ons_local_authority",
    "ons_health_area",
    "ons_postcode",
    "ods_health_area",
    "unknown",
)

PROVIDER_SUBTYPES: tuple[str, ...] = (
    "nhs_trust",
    "nhs_health_board",
    "hsc_trust",
    "independent_healthcare",
    "nhs_organisation",
    "social_care",
    "primary_medical",
    "dental",
    "ambulance",
    "local_authority",
    "charity",
    "company",
    "individual",
    "unknown",
)


def dictionary_markdown() -> str:
    lines = [
        "# Location reference data dictionary",
        "",
        f"Schema version `{SCHEMA_VERSION}`. Name normalisation `{NORMALISATION_VERSION}`.",
        "",
        "A schema version describes this interface. A build id identifies one produced dataset. "
        "A new build time does not by itself mean the rows changed. Adding a column is compatible "
        "within the same major version. Renaming, removing, or changing the meaning of a column "
        "needs a new major version.",
        "",
        "Empty fields are null. Dates are ISO `YYYY-MM-DD`. Timestamps are UTC. "
        "Identifiers and codes are text. Booleans are `true` or `false`.",
        "",
        "## Joins",
        "",
        "1. `search_entity.entity_id` to `entity_site.entity_id`.",
        "2. `entity_site.location_id` to `location.location_id`.",
        "3. `entity_alias.entity_id` and `entity_identifier.entity_id` to `search_entity.entity_id`.",
        "4. A site entity joins to its site with `search_entity.location_id`. "
        "That column is empty for every other entity type. `entity_id` is `site:` plus the location id, "
        "so the two values are not the same.",
        "",
        "A country, county, provider, or other entity returns the current sites linked to it. "
        "That is not a certified population of every healthcare setting in the area. "
        "A provider can cover more than one county. A site's county does not say which provider runs it.",
        "",
        "## How display names are chosen",
        "",
        "Provider names prefer the organisation's own register. "
        "If the Care Quality Commission records the same name apart from case, the Care Quality Commission casing is kept. "
        "Otherwise the name that appears on the most sites is used, and the lowest name breaks a tie. "
        "The same rule, most frequent then lowest, chooses any other entity whose source rows disagree. "
        "A case-only difference is kept as its own alias so the original text remains available.",
        "",
        "## Name normalisation",
        "",
        f"`{NORMALISATION_VERSION}` upper-cases the text, strips accents, turns `&` into `AND`, "
        "drops apostrophes, and turns every other run of punctuation or spacing into a single space. "
        "It does not remove words. `match_string` is a separate discovery field: it also removes common words "
        "and mixes in the parent, town, postcode and codes. Compare names with `entity_alias`, not with `match_string`.",
        "",
        "A value that normalisation reduces to nothing is kept, with `normalisation_status` "
        "`empty_after_normalisation` and an empty `alias_normalised`. The same normalised name may belong to several entities.",
        "",
        "## Identifiers",
        "",
        "`location_id` is `md5` of a prefix and the governing source value:",
        "",
        "| Basis | Input |",
        "| --- | --- |",
        "| `ods` | `ods:` and the Organisation Data Service site code |",
        "| `cqc` | `cqc:` and the Care Quality Commission location id |",
        "| `phs` | `phs:` and the Public Health Scotland hospital or practice code |",
        "| `ciw` | `ciw:` and the Care Inspectorate Wales service URN |",
        "| `care_inspectorate` | `care_inspectorate:` and the Care Inspectorate service id |",
        "| `rqia` | `rqia:` and the RQIA service id |",
        "| `hsc_seed` | `hsc:` and the manually maintained `site_key` on the Northern Ireland hospital list |",
        "",
        "An England Care Quality Commission location uses the Organisation Data Service basis when its organisation "
        "code appears on exactly one current Care Quality Commission location. A later change in that count changes "
        "`location_id`. The identifier table keeps both codes. That change is a transition, not a guarantee that the "
        "surrogate stayed put.",
        "",
        "A provider key is `provider:` plus the organisation code. The `provider:` prefix is the entity type. "
        "The issuing system is `identifier_system`. Organisation Data Service codes and Care Quality Commission "
        "provider ids of the form `1-…` stay distinct. Where the Care Quality Commission uses an Organisation Data "
        "Service organisation code, the published system is `ods`.",
        "",
        "Northern Ireland hospital keys are manually maintained. `site_key` was first written from the upper-case "
        "name and the postcode with the space removed, and that text is now stored on the hospital list. Changing "
        "the name or postcode columns does not change `location_id`. Changing `site_key` does, and the new value is "
        "a different site. RQIA provider keys are `derived`: the register has no provider id, so the key is an md5 "
        "of the provider name. A name change mints a new provider key. No other identifier is minted from a display name.",
        "",
        "Entity ids are not replaced on a rebuild when the governing source value is unchanged. "
        "A change of name, spelling, address, or row order does not change them.",
        "",
        "## Membership",
        "",
        "| membership_type | Meaning |",
        "| --- | --- |",
        "| `self` | The site entity for that site. |",
        "| `provider` | The organisation recorded as running the site. |",
        "| `postcode` | The site's own postcode. |",
        "| `geography` | Country, region, county, or local authority from the postcode lookup, or the country recorded on the source when the postcode is not in the lookup. |",
        "| `health_area` | Integrated care board, health board, or HSC trust area. |",
        "",
        "These are current reference links. "
        "A missing county is normal outside England, and for English unitary authorities. "
        "Health boards, integrated care boards and HSC trust areas are different entity types.",
        "",
        "NHS trusts, Welsh health boards, Scottish health boards and HSC trusts are included even when they have "
        "no current site (`site_count` 0). Independent providers are included only when a current site records them. "
        "Provider subtype comes from the organisation register or, failing that, from one Care Quality Commission "
        "sector or one Care Inspectorate Wales provider type. It is `unknown`, and `entity_subtype_source` is empty, "
        "when those sources do not agree or do not classify the organisation. It is never guessed from the name.",
        "",
        "## Code lists",
        "",
        "Identifier systems: " + ", ".join(f"`{item}`" for item in IDENTIFIER_SYSTEMS) + ".",
        "",
        "Provider subtypes: " + ", ".join(f"`{item}`" for item in PROVIDER_SUBTYPES) + ".",
        "",
        "`nhs_code` on a site is not one system. Use `nhs_code_system`. "
        "`unknown` means a provider code is published but the source does not say which organisation issued it. "
        "The same text under `ods` or `cqc_provider` is a different identifier.",
        "",
        "## Tables",
        "",
    ]
    for table in TABLES:
        keys = ", ".join(f"`{key}`" for key in table.keys)
        lines.extend(
            [
                f"### `{table.filename}`",
                "",
                table.grain + f" Key: {keys}.",
                "",
                "| Column | Type | Nullable | Meaning |",
                "| --- | --- | --- | --- |",
            ]
        )
        for column in table.columns:
            nullable = "yes" if column.nullable else "no"
            lines.append(
                f"| `{column.name}` | {column.logical_type} | {nullable} | {column.description} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Build manifest",
            "",
            "`manifest.json` describes one build. `schema_version` is this interface. `contract_sha256` hashes the "
            "output filenames, keys and columns, so a shape change is visible even when the schema version is unchanged. "
            "`build_id` identifies one produced dataset and starts with the UTC build time. `built_at` is when the "
            "tables were produced. `commit` is the git commit. `worktree_dirty` is true when that commit had uncommitted "
            "changes; a release built from a clean checkout is false. `data_scope` is `current`. `build_status` is "
            "`normal`, `degraded`, `partial`, `sample` or `fixture`. `data_fingerprint` hashes the five reference CSV "
            "checksums, so a new build time with the same fingerprint means those rows did not change.",
            "",
            "`outputs` lists the files inside the zip. Each table entry has its filename, row count, byte size, "
            "SHA-256, grain, keys, ordered `columns` (`name`, `type`, `nullable`) and a `nulls` count per column. "
            "An empty value is unknown. A column this contract does not list is not in the file. `parquet` lists the "
            "Parquet files published beside the zip. Those files are not inside the zip.",
            "",
            "The column definitions in the zip are `data_dictionary.md`.",
            "",
            "## CSV",
            "",
            "UTF-8 without a byte order mark. Comma separator. Fields that contain a comma, quote, or line break "
            "are wrapped in double quotes, and a quote inside a field is doubled. Line endings are line feeds. "
            "An empty field is null. Dates are `YYYY-MM-DD`. Rows are sorted by the key columns.",
            "",
        ]
    )
    return "\n".join(lines)


def attribution_markdown(year: int) -> str:
    return "\n".join(
        [
            "# Attribution",
            "",
            "NHS organisation data from NHS England, care location data from the Care Quality Commission, "
            "Welsh care services from Care Inspectorate Wales, Scottish hospitals, GP practices and health board "
            "geography from Public Health Scotland, Scottish care services from the Care Inspectorate, "
            "Northern Ireland regulated services from RQIA, the Northern Ireland hospital list maintained with "
            "this reference, and postcode geography from the Office for National Statistics, used under the "
            "Open Government Licence "
            "(https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).",
            "",
            f"Contains OS data © Crown copyright and database right {year}.",
            f"Contains Royal Mail data © Royal Mail copyright and database right {year}.",
            f"Contains National Statistics data © Crown copyright and database right {year}.",
            "",
        ]
    )


def coverage_markdown(manifest: dict) -> str:
    status = manifest.get("build_status") or "unknown"
    lines = [
        "# Coverage",
        "",
        f"Build `{manifest.get('build_id', '')}` at `{manifest.get('built_at', '')}`. "
        f"Schema `{manifest.get('schema_version', SCHEMA_VERSION)}`. "
        f"Status `{status}`. Scope `{manifest.get('data_scope', 'current')}`.",
        "",
        "Status values:",
        "",
        "| Status | Meaning |",
        "| --- | --- |",
        "| `normal` | Every source was fetched for this build. |",
        "| `degraded` | At least one source could not be fetched. Its last good copy was used. |",
        "| `partial` | At least one source was left out. Its sites are absent, not carried forward. |",
        "| `sample` | Bundled demonstration rows. Not a full snapshot. |",
        "| `fixture` | Tiny project used to test the models. Not a full snapshot. |",
        "",
        "Do not use a `sample` or `fixture` bundle as the reference snapshot.",
        "",
        "A successful build does not mean every publisher file is newly current. "
        "`publisher_date` is the publisher's edition date. `checked_at` is when this refresh looked at the file. "
        "`built_at` is when these tables were produced. `coverage_effect` is `included`, `last_good_copy`, or `omitted`.",
        "",
        "## What is included",
        "",
        "Current sites in England, Wales, Scotland and Northern Ireland.",
        "",
        "- England: NHS trusts and sites, independent healthcare providers and their sites, and Care Quality Commission locations, including care homes.",
        "- Wales: health boards and their sites, GP practices, and adult services registered with Care Inspectorate Wales.",
        "- Scotland: Public Health Scotland hospitals and GP practices, and adult services registered with the Care Inspectorate.",
        "- Northern Ireland: GP practices, adult services registered with RQIA, and a checked list of HSC hospitals.",
        "",
        "Each site is placed with the Office for National Statistics postcode lookup. "
        "The health area is an integrated care board in England, a health board in Wales and Scotland, "
        "and an HSC trust area in Northern Ireland. Region and county are filled for England.",
        "",
        "Places you can select: country, region, county, local authority, integrated care board, health board, "
        "HSC trust area, postcode, provider and site. NHS trusts, health boards and HSC trusts remain in "
        "`search_entity` when they have no current site. Independent providers without a current site do not.",
        "",
        "## What is not included",
        "",
        "- Independent hospitals and clinics in Wales and Scotland. Those inspectorates do not publish a bulk list.",
        "- Community sites in Northern Ireland, and any closure date for the checked hospital list.",
        "- Welsh branch surgeries.",
        "- Closed sites, previous names, and previous organisational membership.",
        "- A history of mergers. A renamed organisation is not linked to the one it replaced.",
        "- Pharmacies and dental practices as their own service. A dental service registered as a care location is `other`.",
        "",
        "An entity that disappears in a later build may have left the source file or moved outside this coverage. "
        "That is not, by itself, evidence that the service closed.",
        "",
        "The rows are the current reference. They do not say which organisation ran a site on an earlier date.",
        "",
        "## Sources in this build",
        "",
        "| Source | Status | Publisher date | Checked | Coverage |",
        "| --- | --- | --- | --- | --- |",
    ]
    for source in manifest.get("sources") or []:
        lines.append(
            "| {key} | {status} | {publisher_date} | {checked_at} | {coverage_effect} |".format(
                key=source.get("key") or "",
                status=source.get("status") or "",
                publisher_date=source.get("publisher_date") or "",
                checked_at=source.get("checked_at") or "",
                coverage_effect=source.get("coverage_effect") or "",
            )
        )
    if not manifest.get("sources"):
        lines.append("|  |  |  |  |  |")
    lines.extend(["", "Licence and attribution are in `ATTRIBUTION.md`.", ""])
    return "\n".join(lines)

-- Archived CQC locations. Kept for history; excluded from current marts.
with source as (
    select * from {{ read_header_csv('cqc/deactivated_locations.csv') }}
)

select
    nullif(trim(cqc_location_id), '') as cqc_location_id,
    nullif(trim(name), '') as name,
    nullif(upper(trim(ods_code)), '') as ods_code,
    nullif(trim(postcode), '') as postcode,
    coalesce(
        try_strptime(nullif(trim(valid_from), ''), '%Y-%m-%d'),
        try_strptime(nullif(trim(valid_from), ''), '%d/%m/%Y')
    )::date as valid_from,
    coalesce(
        try_strptime(nullif(trim(valid_to), ''), '%Y-%m-%d'),
        try_strptime(nullif(trim(valid_to), ''), '%d/%m/%Y')
    )::date as valid_to
from source
where nullif(trim(cqc_location_id), '') is not null

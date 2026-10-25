with source as (
    select * from {{ read_header_csv('cqc/locations.csv') }}
)

select
    nullif(trim(cqc_location_id), '') as cqc_location_id,
    nullif(trim(name), '') as name,
    nullif(upper(trim(ods_code)), '') as ods_code,
    nullif(trim(postcode), '') as postcode,
    nullif(trim(town), '') as town,
    nullif(trim(address_1), '') as address_1,
    nullif(trim(address_2), '') as address_2,
    nullif(
        nullif(regexp_replace(trim(brand_name), '^BRAND\s+', ''), ''),
        '-'
    ) as brand_name,
    nullif(trim(provider_id), '') as provider_id,
    nullif(trim(provider_name), '') as provider_name,
    nullif(upper(trim(care_home)), '') as care_home,
    nullif(trim(sector), '') as sector,
    nullif(trim(primary_category), '') as primary_category,
    nullif(trim(region_name), '') as region_name,
    nullif(trim(local_authority_name), '') as local_authority_name,
    coalesce(
        try_strptime(nullif(trim(valid_from), ''), '%Y-%m-%d'),
        try_strptime(nullif(trim(valid_from), ''), '%d/%m/%Y')
    )::date as valid_from,
    nullif(upper(trim(dormant)), '') as dormant
from source
where nullif(trim(cqc_location_id), '') is not null

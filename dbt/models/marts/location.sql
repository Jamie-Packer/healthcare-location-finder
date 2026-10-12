with sites as (
    select
        *,
        trim(regexp_replace(
            upper(concat_ws(
                ' ',
                name,
                ods_name,
                brand_name,
                parent_name,
                town,
                postcode,
                postcode_compact,
                ods_code,
                cqc_location_id
            )),
            '[^A-Z0-9]+',
            ' ',
            'g'
        )) as match_string
    from {{ ref('int_sites') }}
)

select
    location_id,
    name,
    match_string,
    parent_name,
    parent_code,
    postcode,
    postcode_compact,
    town,
    local_authority_name,
    local_authority_code,
    county_name,
    county_code,
    region_name,
    region_code,
    icb_name,
    icb_code,
    icb_ods_code,
    country_name,
    ods_code,
    cqc_location_id,
    service_type,
    valid_from,
    valid_to
from sites

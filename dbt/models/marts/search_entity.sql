with sites as (
    select * from {{ ref('location') }}
),

entities as (
    select
        'country:' || country_name as entity_id,
        'country' as entity_type,
        country_name as name,
        cast(null as varchar) as code,
        upper(country_name) as search_text,
        location_id
    from sites
    where country_name is not null

    union all

    select
        'region:' || region_code,
        'region',
        region_name,
        region_code,
        upper(concat_ws(' ', region_name, region_code)),
        location_id
    from sites
    where region_code is not null and region_name is not null

    union all

    select
        'county:' || county_code,
        'county',
        county_name,
        county_code,
        upper(concat_ws(' ', county_name, county_code)),
        location_id
    from sites
    where county_code is not null and county_name is not null

    union all

    select
        'local_authority:' || local_authority_code,
        'local_authority',
        local_authority_name,
        local_authority_code,
        upper(concat_ws(' ', local_authority_name, local_authority_code)),
        location_id
    from sites
    where local_authority_code is not null and local_authority_name is not null

    union all

    select
        health_area_type || ':' || health_area_code,
        health_area_type,
        health_area_name,
        coalesce(health_area_ods_code, health_area_code),
        upper(concat_ws(' ', health_area_name, health_area_code, health_area_ods_code)),
        location_id
    from sites
    where health_area_code is not null
        and health_area_name is not null
        and health_area_type is not null

    union all

    select
        'postcode:' || postcode_compact,
        'postcode',
        postcode,
        postcode_compact,
        upper(concat_ws(' ', postcode, postcode_compact)),
        location_id
    from sites
    where postcode_compact is not null

    union all

    select
        'provider:' || parent_code,
        'provider',
        parent_name,
        parent_code,
        upper(concat_ws(' ', parent_name, parent_code)),
        location_id
    from sites
    where parent_code is not null and parent_name is not null

    union all

    select
        'site:' || location_id,
        'site',
        name,
        coalesce(nhs_code, regulator_id),
        upper(concat_ws(' ', name, nhs_code, regulator_id, postcode, postcode_compact)),
        location_id
    from sites
    where name is not null
),

searchable as (
    select
        entity_id,
        any_value(entity_type) as entity_type,
        any_value(name) as name,
        any_value(code) as code,
        any_value(search_text) as search_text
    from entities
    group by entity_id
)

select * from searchable

with sites as (
    select * from {{ ref('int_sites') }}
),

providers as (
    select * from {{ ref('int_providers') }}
),

candidates as (
    select
        'country:' || country_name as entity_id,
        'country' as entity_type,
        country_name as name,
        cast(null as varchar) as code,
        cast(null as varchar) as code_system,
        upper(country_name) as search_text,
        location_id,
        'geography' as membership_type,
        country_source as membership_source,
        cast(null as varchar) as entity_subtype,
        cast(null as varchar) as entity_subtype_source
    from sites
    where country_name is not null

    union all

    select
        'region:' || region_code,
        'region',
        region_name,
        region_code,
        'ons_region',
        upper(concat_ws(' ', region_name, region_code)),
        location_id,
        'geography',
        'ons_postcode',
        null,
        null
    from sites
    where region_code is not null and region_name is not null

    union all

    select
        'county:' || county_code,
        'county',
        county_name,
        county_code,
        'ons_county',
        upper(concat_ws(' ', county_name, county_code)),
        location_id,
        'geography',
        'ons_postcode',
        null,
        null
    from sites
    where county_code is not null and county_name is not null

    union all

    select
        'local_authority:' || local_authority_code,
        'local_authority',
        local_authority_name,
        local_authority_code,
        'ons_local_authority',
        upper(concat_ws(' ', local_authority_name, local_authority_code)),
        location_id,
        'geography',
        'ons_postcode',
        null,
        null
    from sites
    where local_authority_code is not null and local_authority_name is not null

    union all

    select
        health_area_type || ':' || health_area_code,
        health_area_type,
        health_area_name,
        coalesce(health_area_ods_code, health_area_code),
        case
            when health_area_ods_code is not null and health_area_type = 'hsc_trust' then 'hsc_trust'
            when health_area_ods_code is not null then 'ods_health_area'
            when health_area_type = 'health_board' and health_area_code like 'S%' then 'phs_health_board'
            when health_area_type = 'hsc_trust' then 'hsc_trust'
            else 'ons_health_area'
        end,
        upper(concat_ws(' ', health_area_name, health_area_code, health_area_ods_code)),
        location_id,
        'health_area',
        health_area_source,
        null,
        null
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
        'ons_postcode',
        upper(concat_ws(' ', postcode, postcode_compact)),
        location_id,
        'postcode',
        'site_record',
        null,
        null
    from sites
    where postcode_compact is not null

    union all

    select
        'provider:' || sites.parent_code,
        'provider',
        providers.provider_name,
        sites.parent_code,
        providers.code_system,
        upper(concat_ws(' ', providers.provider_name, sites.parent_code)),
        sites.location_id,
        'provider',
        sites.source,
        providers.entity_subtype,
        providers.entity_subtype_source
    from sites
    inner join providers
        on providers.provider_code = sites.parent_code

    union all

    select
        'provider:' || provider_code,
        'provider',
        provider_name,
        provider_code,
        code_system,
        upper(concat_ws(' ', provider_name, provider_code)),
        cast(null as varchar),
        cast(null as varchar),
        cast(null as varchar),
        entity_subtype,
        entity_subtype_source
    from providers
    where site_count = 0

    union all

    select
        'site:' || location_id,
        'site',
        name,
        coalesce(nhs_code, regulator_id),
        case
            when nhs_code is not null then nhs_code_system
            else regulator_id_system
        end,
        upper(concat_ws(' ', name, nhs_code, regulator_id, postcode, postcode_compact)),
        location_id,
        'self',
        'location',
        null,
        null
    from sites
    where name is not null
)

select * from candidates

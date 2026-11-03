with sites as (
    select * from {{ ref('int_sites') }}
),

raw as (
    select
        'site:' || location_id as entity_id,
        nhs_code_system as identifier_system,
        nhs_code as identifier_value,
        'source_assigned' as identifier_origin,
        case
            when location_id_basis in ('ods', 'phs') then 'primary'
            else 'additional'
        end as identifier_role,
        source
    from sites
    where nhs_code is not null

    union all

    select
        'site:' || location_id,
        regulator_id_system,
        regulator_id,
        'source_assigned',
        case
            when location_id_basis in ('cqc', 'ciw', 'care_inspectorate', 'rqia') then 'primary'
            else 'additional'
        end,
        source
    from sites
    where regulator_id is not null

    union all

    select
        'site:' || location_id,
        'hsc_seed',
        seed_key,
        'manually_maintained',
        'primary',
        'hsc'
    from sites
    where seed_key is not null

    union all

    select
        'provider:' || provider_code,
        code_system,
        provider_code,
        identifier_origin,
        'primary',
        coalesce(
            entity_subtype_source,
            case code_system
                when 'cqc_provider' then 'cqc'
                when 'ciw_provider' then 'ciw'
                when 'care_inspectorate_provider' then 'care_inspectorate'
                when 'rqia_provider' then 'rqia'
                when 'phs_health_board' then 'phs'
                when 'hsc_trust' then 'ni_hsc_trust_seed'
                when 'ods' then 'ods'
                else 'site_record'
            end
        )
    from {{ ref('int_providers') }}

    union all

    select distinct
        'region:' || region_code,
        'ons_region',
        region_code,
        'source_assigned',
        'primary',
        'ons'
    from sites
    where region_code is not null and region_name is not null

    union all

    select distinct
        'county:' || county_code,
        'ons_county',
        county_code,
        'source_assigned',
        'primary',
        'ons'
    from sites
    where county_code is not null and county_name is not null

    union all

    select distinct
        'local_authority:' || local_authority_code,
        'ons_local_authority',
        local_authority_code,
        'source_assigned',
        'primary',
        'ons'
    from sites
    where local_authority_code is not null and local_authority_name is not null

    union all

    select distinct
        health_area_type || ':' || health_area_code,
        case
            when health_area_type = 'health_board' and health_area_code like 'S%' then 'phs_health_board'
            when health_area_type = 'hsc_trust' then 'hsc_trust'
            else 'ons_health_area'
        end,
        health_area_code,
        case
            when health_area_type = 'hsc_trust' then 'manually_maintained'
            else 'source_assigned'
        end,
        'primary',
        coalesce(health_area_source, 'ons')
    from sites
    where health_area_code is not null
        and health_area_name is not null
        and health_area_type is not null

    union all

    select distinct
        health_area_type || ':' || health_area_code,
        'ods_health_area',
        health_area_ods_code,
        'source_assigned',
        'additional',
        'ons'
    from sites
    where health_area_code is not null
        and health_area_name is not null
        and health_area_type is not null
        and health_area_ods_code is not null
        and health_area_ods_code <> health_area_code

    union all

    select distinct
        'postcode:' || postcode_compact,
        'ons_postcode',
        postcode_compact,
        'source_assigned',
        'primary',
        'site_record'
    from sites
    where postcode_compact is not null
)

select
    entity_id,
    identifier_system,
    identifier_value,
    identifier_origin,
    identifier_role,
    source
from raw
where identifier_system is not null
    and identifier_value is not null
qualify row_number() over (
    partition by entity_id, identifier_system, identifier_value, source
    order by case when identifier_role = 'primary' then 0 else 1 end
) = 1

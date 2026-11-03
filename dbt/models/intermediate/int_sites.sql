with sites as (
    select * from {{ ref('int_england_sites') }}
    union all
    select * from {{ ref('int_other_sites') }}
),

placed as (
    select
        sites.location_id,
        sites.name,
        sites.alt_name,
        sites.brand_name,
        sites.nhs_code,
        sites.regulator,
        sites.regulator_id,
        sites.parent_name,
        sites.parent_code,
        sites.address,
        sites.postcode,
        sites.postcode_compact,
        sites.town,
        sites.care_home,
        sites.primary_category,
        sites.service_category,
        sites.source,
        sites.origin,
        sites.valid_from,
        cast(null as date) as valid_to,
        case
            when geo.country_name in ('England', 'Wales', 'Scotland', 'Northern Ireland') then geo.country_name
            else sites.country_fallback
        end as country_name,
        case
            when geo.country_name = 'England' or (
                geo.country_name is null and sites.country_fallback = 'England'
            ) then coalesce(geo.region_name, sites.cqc_region_name)
        end as region_name,
        case
            when geo.country_name = 'England' or (
                geo.country_name is null and sites.country_fallback = 'England'
            ) then geo.region_code
        end as region_code,
        case
            when geo.country_name = 'England' or (
                geo.country_name is null and sites.country_fallback = 'England'
            ) then geo.county_name
        end as county_name,
        case
            when geo.country_name = 'England' or (
                geo.country_name is null and sites.country_fallback = 'England'
            ) then geo.county_code
        end as county_code,
        coalesce(
            geo.local_authority_name,
            case
                when geo.country_name = 'England' or (
                    geo.country_name is null and sites.country_fallback = 'England'
                ) then sites.cqc_local_authority_name
            end
        ) as local_authority_name,
        geo.local_authority_code,
        case
            when sites.source_health_code is not null or sites.source_health_name is not null
                then sites.source_health_code
            else coalesce(geo.health_area_code, icb_by_ods.code)
        end as health_area_code,
        case
            when sites.source_health_code is not null or sites.source_health_name is not null
                then sites.source_health_name
            else coalesce(geo.health_area_name, icb_by_ods.name)
        end as health_area_name,
        case
            when sites.source_health_code is not null or sites.source_health_name is not null
                then sites.source_health_type
            else coalesce(
                geo.health_area_type,
                case when icb_by_ods.code is not null then 'icb' end
            )
        end as health_area_type,
        case
            when sites.source_health_code is not null or sites.source_health_name is not null
                then sites.source_health_code
            else coalesce(geo.health_area_ods_code, icb_by_ods.ods_code)
        end as health_area_ods_code,
        mapped.service_type as mapped_service_type,
        sites.seed_key,
        geo.postcode_compact is not null as postcode_matched,
        case
            when geo.country_name in ('England', 'Wales', 'Scotland', 'Northern Ireland') then 'ons_postcode'
            else 'country_fallback'
        end as country_source,
        case
            when sites.source_health_code is not null or sites.source_health_name is not null then 'source_record'
            when geo.health_area_code is not null or geo.health_area_name is not null then 'ons_postcode'
            when icb_by_ods.code is not null then 'ods_icb_code'
        end as health_area_source
    from sites
    left join {{ ref('int_postcode_geography') }} as geo
        on sites.postcode_compact = geo.postcode_compact
    left join {{ ref('stg_geography_names') }} as icb_by_ods
        on icb_by_ods.area_type = 'icb'
        and icb_by_ods.ods_code = sites.ods_icb_code
        and (
            geo.country_code = 'E92000001'
            or (geo.country_code is null and sites.country_fallback = 'England')
        )
    left join {{ ref('service_type_map') }} as mapped
        on mapped.source = sites.source
        and mapped.category = sites.service_category
)

select
    location_id,
    name,
    alt_name,
    brand_name,
    nhs_code,
    regulator,
    regulator_id,
    parent_name,
    parent_code,
    address,
    postcode,
    postcode_compact,
    town,
    local_authority_name,
    local_authority_code,
    county_name,
    county_code,
    region_name,
    region_code,
    health_area_name,
    health_area_code,
    health_area_ods_code,
    health_area_type,
    country_name,
    country_source,
    source,
    valid_from,
    valid_to,
    seed_key,
    postcode_matched,
    health_area_source,
    case
        when source = 'ciw' then alt_name
    end as known_as,
    case
        when source = 'ods'
            and country_name = 'Northern Ireland'
            and service_category = 'gp'
            then alt_name
    end as address_name,
    case
        when nhs_code is null then null
        when source = 'phs' and service_category = 'hospital' then 'phs_hospital'
        when source = 'phs' and service_category = 'gp' then 'phs_practice'
        else 'ods'
    end as nhs_code_system,
    case regulator
        when 'CQC' then 'cqc_location'
        when 'CIW' then 'ciw_service'
        when 'Care Inspectorate' then 'care_inspectorate_service'
        when 'RQIA' then 'rqia_service'
    end as regulator_id_system,
    case
        when source = 'hsc' then 'hsc_seed'
        when nhs_code is not null and location_id = md5('ods:' || nhs_code) then 'ods'
        when regulator = 'CQC' and location_id = md5('cqc:' || regulator_id) then 'cqc'
        when source = 'phs' and location_id = md5('phs:' || nhs_code) then 'phs'
        when regulator = 'CIW' and location_id = md5('ciw:' || regulator_id) then 'ciw'
        when regulator = 'Care Inspectorate' and location_id = md5('care_inspectorate:' || regulator_id)
            then 'care_inspectorate'
        when regulator = 'RQIA' and location_id = md5('rqia:' || regulator_id) then 'rqia'
    end as location_id_basis,
    case
        when parent_code is null then null
        when source = 'rqia' then 'rqia_provider'
        when source = 'ciw' then 'ciw_provider'
        when source = 'care_inspectorate' then 'care_inspectorate_provider'
        when source = 'phs' then 'phs_health_board'
        when source = 'hsc' then 'hsc_trust'
        when country_name = 'Northern Ireland' and parent_code like 'ZT%' then 'hsc_trust'
        when parent_code in (
            select organisation_code from {{ ref('stg_ods_trusts') }} where valid_to is null
            union
            select organisation_code from {{ ref('stg_ods_independent_providers') }} where valid_to is null
            union
            select organisation_code from {{ ref('stg_ods_welsh_boards') }} where valid_to is null
        ) then 'ods'
        when source = 'cqc' then 'cqc_provider'
        when source in ('ods', 'ods+cqc') then 'ods'
        else 'unknown'
    end as parent_code_system,
    case
        when origin = 'england' and care_home = 'Y' then 'care home'
        when origin = 'england' and (
            coalesce(primary_category, '') ilike '%hospital%'
            or name ilike '%hospital%'
            or coalesce(alt_name, '') ilike '%hospital%'
        ) then 'hospital'
        when origin = 'england' and (
            coalesce(primary_category, '') ilike 'gp%'
            or coalesce(primary_category, '') ilike '%general practice%'
        ) then 'gp'
        when origin = 'england'
            and primary_category = 'Community based adult social care services'
            then 'home care'
        when origin = 'england' then 'other'
        when service_category in ('gp', 'hospital') then service_category
        when mapped_service_type <> 'other' then mapped_service_type
        when name ilike '%hospital%' or coalesce(alt_name, '') ilike '%hospital%' then 'hospital'
        else 'other'
    end as service_type
from placed
where country_name in ('England', 'Wales', 'Scotland', 'Northern Ireland')

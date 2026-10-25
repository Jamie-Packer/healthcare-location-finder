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
        mapped.service_type as mapped_service_type
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
    source,
    valid_from,
    valid_to,
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

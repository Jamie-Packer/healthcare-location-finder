{{ config(materialized='table') }}

with open_ods as (
    select
        organisation_code,
        name,
        icb_code,
        town,
        postcode,
        nullif(upper(replace(postcode, ' ', '')), '') as postcode_compact,
        valid_from,
        parent_organisation_code,
        site_kind
    from {{ ref('stg_ods_trust_sites') }}
    where valid_to is null
        and coalesce(role_id, '') not ilike '%RO31%'
    union all
    select
        organisation_code,
        name,
        icb_code,
        town,
        postcode,
        nullif(upper(replace(postcode, ' ', '')), '') as postcode_compact,
        valid_from,
        parent_organisation_code,
        site_kind
    from {{ ref('stg_ods_independent_sites') }}
    where valid_to is null
        and coalesce(role_id, '') not ilike '%RO31%'
),

current_cqc as (
    select
        *,
        nullif(upper(replace(postcode, ' ', '')), '') as postcode_compact
    from {{ ref('stg_cqc_locations') }}
    where coalesce(dormant, 'N') <> 'Y'
),

code_counts as (
    select ods_code, count(*) as cqc_count
    from current_cqc
    where ods_code is not null
    group by 1
),

orgs as (
    select organisation_code, any_value(name) as name
    from (
        select organisation_code, name
        from {{ ref('stg_ods_trusts') }}
        where valid_to is null
        union all
        select organisation_code, name
        from {{ ref('stg_ods_independent_providers') }}
        where valid_to is null
    ) parents
    group by 1
),

merged as (
    select
        md5('ods:' || ods.organisation_code) as location_id,
        coalesce(cqc.name, ods.name) as name,
        ods.name as ods_name,
        cqc.brand_name,
        ods.organisation_code as ods_code,
        cqc.cqc_location_id,
        coalesce(orgs.name, cqc.provider_name) as parent_name,
        coalesce(ods.parent_organisation_code, cqc.provider_id) as parent_code,
        coalesce(cqc.postcode, ods.postcode) as postcode,
        coalesce(cqc.postcode_compact, ods.postcode_compact) as postcode_compact,
        coalesce(cqc.town, ods.town) as town,
        cqc.care_home,
        cqc.primary_category,
        cqc.region_name as cqc_region_name,
        cqc.local_authority_name as cqc_local_authority_name,
        ods.icb_code as ods_icb_code,
        coalesce(cqc.valid_from, ods.valid_from) as valid_from,
        ods.site_kind,
        true as from_cqc
    from open_ods as ods
    inner join current_cqc as cqc
        on ods.organisation_code = cqc.ods_code
    inner join code_counts
        on cqc.ods_code = code_counts.ods_code
        and code_counts.cqc_count = 1
    left join orgs
        on ods.parent_organisation_code = orgs.organisation_code
),

ods_only as (
    select
        md5('ods:' || ods.organisation_code) as location_id,
        ods.name,
        ods.name as ods_name,
        cast(null as varchar) as brand_name,
        ods.organisation_code as ods_code,
        cast(null as varchar) as cqc_location_id,
        orgs.name as parent_name,
        ods.parent_organisation_code as parent_code,
        ods.postcode,
        ods.postcode_compact,
        ods.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        ods.icb_code as ods_icb_code,
        ods.valid_from,
        ods.site_kind,
        false as from_cqc
    from open_ods as ods
    left join code_counts
        on ods.organisation_code = code_counts.ods_code
    left join orgs
        on ods.parent_organisation_code = orgs.organisation_code
    where code_counts.ods_code is null
),

cqc_rest as (
    select
        case
            when cqc.ods_code is not null and coalesce(code_counts.cqc_count, 0) = 1
                then md5('ods:' || cqc.ods_code)
            else md5('cqc:' || cqc.cqc_location_id)
        end as location_id,
        cqc.name,
        cast(null as varchar) as ods_name,
        cqc.brand_name,
        cqc.ods_code,
        cqc.cqc_location_id,
        cqc.provider_name as parent_name,
        cqc.provider_id as parent_code,
        cqc.postcode,
        cqc.postcode_compact,
        cqc.town,
        cqc.care_home,
        cqc.primary_category,
        cqc.region_name as cqc_region_name,
        cqc.local_authority_name as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cqc.valid_from,
        cast(null as varchar) as site_kind,
        true as from_cqc
    from current_cqc as cqc
    left join code_counts
        on cqc.ods_code = code_counts.ods_code
    where cqc.cqc_location_id not in (select cqc_location_id from merged)
),

sites as (
    select * from merged
    union all
    select * from ods_only
    union all
    select * from cqc_rest
),

placed as (
    select
        sites.location_id,
        sites.name,
        sites.ods_name,
        sites.brand_name,
        sites.ods_code,
        sites.cqc_location_id,
        sites.parent_name,
        sites.parent_code,
        sites.postcode,
        sites.postcode_compact,
        sites.town,
        sites.care_home,
        sites.primary_category,
        sites.site_kind,
        sites.valid_from,
        cast(null as date) as valid_to,
        sites.from_cqc,
        geo.country_code,
        geo.region_code,
        geo.county_code,
        geo.local_authority_code,
        coalesce(geo.icb_code, icb_by_ods.code) as icb_code,
        icb_by_ods.ods_code as icb_ods_code,
        coalesce(countries.name, case when sites.from_cqc then 'England' end) as country_name,
        coalesce(regions.name, sites.cqc_region_name) as region_name,
        counties.name as county_name,
        coalesce(local_authorities.name, sites.cqc_local_authority_name) as local_authority_name,
        coalesce(icb_by_stat.name, icb_by_ods.name) as icb_name
    from sites
    left join {{ ref('stg_nspl_postcodes') }} as geo
        on sites.postcode_compact = geo.postcode_compact
    left join {{ ref('stg_geography_names') }} as countries
        on countries.area_type = 'country'
        and countries.code = geo.country_code
    left join {{ ref('stg_geography_names') }} as regions
        on regions.area_type = 'region'
        and regions.code = geo.region_code
    left join {{ ref('stg_geography_names') }} as counties
        on counties.area_type = 'county'
        and counties.code = geo.county_code
    left join {{ ref('stg_geography_names') }} as local_authorities
        on local_authorities.area_type = 'local_authority'
        and local_authorities.code = geo.local_authority_code
    left join {{ ref('stg_geography_names') }} as icb_by_stat
        on icb_by_stat.area_type = 'icb'
        and icb_by_stat.code = geo.icb_code
    left join {{ ref('stg_geography_names') }} as icb_by_ods
        on icb_by_ods.area_type = 'icb'
        and icb_by_ods.ods_code = sites.ods_icb_code
)

select
    location_id,
    name,
    ods_name,
    brand_name,
    ods_code,
    cqc_location_id,
    parent_name,
    parent_code,
    postcode,
    postcode_compact,
    town,
    region_name,
    region_code,
    county_name,
    county_code,
    local_authority_name,
    local_authority_code,
    icb_name,
    icb_code,
    icb_ods_code,
    country_name,
    valid_from,
    valid_to,
    case
        when care_home = 'Y' then 'care home'
        when primary_category ilike '%hospital%'
            or name ilike '%hospital%'
            or coalesce(ods_name, '') ilike '%hospital%'
            then 'hospital'
        when primary_category ilike 'gp%'
            or primary_category ilike '%general practice%'
            then 'gp'
        else 'other'
    end as service_type
from placed
where country_code = 'E92000001'
    or (country_code is null and from_cqc)

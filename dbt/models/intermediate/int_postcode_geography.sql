with postcodes as (
    select * from {{ ref('stg_nspl_postcodes') }}
),

names as (
    select * from {{ ref('stg_geography_names') }}
),

boards as (
    select * from {{ ref('stg_phs_council_board') }}
),

trusts as (
    select
        lcg_code,
        any_value(trust_code) as trust_code,
        any_value(trust_name) as trust_name
    from {{ ref('ni_lcg_trust') }}
    group by lcg_code
)

select
    postcodes.postcode_compact,
    postcodes.country_code,
    postcodes.terminated,
    countries.name as country_name,
    case
        when postcodes.country_code = 'E92000001'
            and coalesce(postcodes.region_code, '') not like '%99999999'
            then postcodes.region_code
    end as region_code,
    case
        when postcodes.country_code = 'E92000001'
            and coalesce(postcodes.region_code, '') not like '%99999999'
            then regions.name
    end as region_name,
    case
        when postcodes.country_code = 'E92000001'
            and coalesce(postcodes.county_code, '') not like '%99999999'
            then postcodes.county_code
    end as county_code,
    case
        when postcodes.country_code = 'E92000001'
            and coalesce(postcodes.county_code, '') not like '%99999999'
            then counties.name
    end as county_name,
    postcodes.local_authority_code,
    local_authorities.name as local_authority_name,
    case
        when postcodes.country_code = 'E92000001' then postcodes.icb_code
        when postcodes.country_code = 'W92000004' and postcodes.sicbl_code like 'W%' then postcodes.sicbl_code
        when postcodes.country_code = 'S92000003' then boards.health_board_code
        when postcodes.country_code = 'N92000002' then trusts.trust_code
    end as health_area_code,
    case
        when postcodes.country_code = 'E92000001' then icb.name
        when postcodes.country_code = 'W92000004' and welsh.name is not null then
            case
                when welsh.name ilike '%board%' then welsh.name
                else welsh.name || ' Health Board'
            end
        when postcodes.country_code = 'S92000003' then boards.health_board_name
        when postcodes.country_code = 'N92000002' then trusts.trust_name
    end as health_area_name,
    case
        when postcodes.country_code = 'E92000001' and postcodes.icb_code is not null then 'icb'
        when postcodes.country_code = 'W92000004' and postcodes.sicbl_code like 'W%' then 'health_board'
        when postcodes.country_code = 'S92000003' and boards.health_board_code is not null then 'health_board'
        when postcodes.country_code = 'N92000002' and trusts.trust_code is not null then 'hsc_trust'
    end as health_area_type,
    case
        when postcodes.country_code = 'E92000001' then icb.ods_code
        when postcodes.country_code = 'W92000004' then welsh.ods_code
        when postcodes.country_code = 'N92000002' then trusts.trust_code
    end as health_area_ods_code
from postcodes
left join names as countries
    on countries.area_type = 'country'
    and countries.code = postcodes.country_code
left join names as regions
    on regions.area_type = 'region'
    and regions.code = postcodes.region_code
left join names as counties
    on counties.area_type = 'county'
    and counties.code = postcodes.county_code
left join names as local_authorities
    on local_authorities.area_type = 'local_authority'
    and local_authorities.code = postcodes.local_authority_code
left join names as icb
    on icb.area_type = 'icb'
    and icb.code = postcodes.icb_code
left join names as welsh
    on welsh.area_type = 'sicbl'
    and welsh.code = postcodes.sicbl_code
left join boards
    on boards.council_code = postcodes.local_authority_code
    and postcodes.country_code = 'S92000003'
left join trusts
    on trusts.lcg_code = postcodes.sicbl_code
    and postcodes.country_code = 'N92000002'

with boards as (
    select health_board_code, any_value(health_board_name) as health_board_name
    from {{ ref('stg_phs_council_board') }}
    group by 1
),

board_names as (
    select
        health_board_code,
        health_board_name,
        lower(regexp_replace(health_board_name, '^NHS\s+', '')) as bare_name
    from boards
),

trusts as (
    select trust_code, any_value(trust_name) as trust_name
    from {{ ref('ni_lcg_trust') }}
    group by 1
),

taken as (
    select nhs_code
    from {{ ref('int_england_sites') }}
    where nhs_code is not null
),

welsh_sites as (
    select
        md5('ods:' || site.organisation_code) as location_id,
        site.name,
        cast(null as varchar) as alt_name,
        cast(null as varchar) as brand_name,
        site.organisation_code as nhs_code,
        cast(null as varchar) as regulator,
        cast(null as varchar) as regulator_id,
        board.name as parent_name,
        site.parent_organisation_code as parent_code,
        {{ address_of(['site.address_line_1', 'site.address_line_2', 'site.address_line_3']) }} as address,
        site.postcode,
        nullif(upper(replace(site.postcode, ' ', '')), '') as postcode_compact,
        site.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        cast(null as varchar) as service_category,
        'ods' as source,
        'other' as origin,
        'Wales' as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        site.valid_from
    from {{ ref('stg_ods_welsh_board_sites') }} as site
    left join {{ ref('stg_ods_welsh_boards') }} as board
        on board.organisation_code = site.parent_organisation_code
        and board.valid_to is null
    where site.valid_to is null
        and site.organisation_code not in (select nhs_code from taken)
),

practices as (
    select
        md5('ods:' || practice.organisation_code) as location_id,
        practice.name,
        practice.alt_name,
        cast(null as varchar) as brand_name,
        practice.organisation_code as nhs_code,
        cast(null as varchar) as regulator,
        cast(null as varchar) as regulator_id,
        coalesce(trust.trust_name, welsh.name) as parent_name,
        coalesce(trust.trust_code, practice.parent_code) as parent_code,
        {{ address_of(['practice.address_line_1', 'practice.address_line_2', 'practice.address_line_3']) }} as address,
        practice.postcode,
        nullif(upper(replace(practice.postcode, ' ', '')), '') as postcode_compact,
        practice.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        'gp' as service_category,
        'ods' as source,
        'other' as origin,
        practice.nation as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        practice.valid_from
    from {{ ref('stg_ods_gp_practices') }} as practice
    left join {{ ref('ni_lcg_trust') }} as trust
        on trust.lcg_code = practice.parent_code
    left join {{ ref('stg_ods_welsh_boards') }} as welsh
        on welsh.organisation_code = practice.parent_code
        and welsh.valid_to is null
    where practice.valid_to is null
        and practice.organisation_code not in (select nhs_code from taken)
),

hospitals as (
    select
        md5('phs:' || hospital.hospital_code) as location_id,
        hospital.name,
        cast(null as varchar) as alt_name,
        cast(null as varchar) as brand_name,
        hospital.hospital_code as nhs_code,
        cast(null as varchar) as regulator,
        cast(null as varchar) as regulator_id,
        boards.health_board_name as parent_name,
        hospital.health_board_code as parent_code,
        hospital.address,
        hospital.postcode,
        nullif(upper(replace(hospital.postcode, ' ', '')), '') as postcode_compact,
        hospital.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        'hospital' as service_category,
        'phs' as source,
        'other' as origin,
        'Scotland' as country_fallback,
        hospital.health_board_code as source_health_code,
        boards.health_board_name as source_health_name,
        'health_board' as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cast(null as date) as valid_from
    from {{ ref('stg_phs_hospitals') }} as hospital
    left join boards
        on boards.health_board_code = hospital.health_board_code
),

scottish_practices as (
    select
        md5('phs:' || practice.practice_code) as location_id,
        practice.name,
        cast(null as varchar) as alt_name,
        cast(null as varchar) as brand_name,
        practice.practice_code as nhs_code,
        cast(null as varchar) as regulator,
        cast(null as varchar) as regulator_id,
        boards.health_board_name as parent_name,
        practice.health_board_code as parent_code,
        practice.address,
        practice.postcode,
        nullif(upper(replace(practice.postcode, ' ', '')), '') as postcode_compact,
        practice.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        'gp' as service_category,
        'phs' as source,
        'other' as origin,
        'Scotland' as country_fallback,
        practice.health_board_code as source_health_code,
        boards.health_board_name as source_health_name,
        'health_board' as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cast(null as date) as valid_from
    from {{ ref('stg_phs_gp_practices') }} as practice
    left join boards
        on boards.health_board_code = practice.health_board_code
),

care_inspectorate as (
    select
        md5('care_inspectorate:' || service.service_id) as location_id,
        service.name,
        cast(null as varchar) as alt_name,
        cast(null as varchar) as brand_name,
        cast(null as varchar) as nhs_code,
        'Care Inspectorate' as regulator,
        service.service_id as regulator_id,
        service.provider_name as parent_name,
        service.provider_id as parent_code,
        {{ address_of(['service.address_1', 'service.address_2', 'service.address_3']) }} as address,
        service.postcode,
        nullif(upper(replace(service.postcode, ' ', '')), '') as postcode_compact,
        service.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        service.service_type as service_category,
        'care_inspectorate' as source,
        'other' as origin,
        'Scotland' as country_fallback,
        board_names.health_board_code as source_health_code,
        board_names.health_board_name as source_health_name,
        case
            when board_names.health_board_code is not null then 'health_board'
        end as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        service.valid_from
    from {{ ref('stg_cis_services') }} as service
    left join board_names
        on board_names.bare_name = lower(service.health_board_name)
),

ciw as (
    select
        md5('ciw:' || service.service_urn) as location_id,
        service.name,
        service.known_as as alt_name,
        cast(null as varchar) as brand_name,
        cast(null as varchar) as nhs_code,
        'CIW' as regulator,
        service.service_urn as regulator_id,
        service.provider_name as parent_name,
        service.provider_urn as parent_code,
        {{ address_of(['service.address_1', 'service.address_2', 'service.address_3']) }} as address,
        service.postcode,
        nullif(upper(replace(service.postcode, ' ', '')), '') as postcode_compact,
        service.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        service.service_type as service_category,
        'ciw' as source,
        'other' as origin,
        'Wales' as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cast(null as date) as valid_from
    from {{ ref('stg_ciw_services') }} as service
),

rqia as (
    select
        md5('rqia:' || service.service_id) as location_id,
        service.name,
        cast(null as varchar) as alt_name,
        cast(null as varchar) as brand_name,
        cast(null as varchar) as nhs_code,
        'RQIA' as regulator,
        service.service_id as regulator_id,
        service.provider_name as parent_name,
        case
            when service.provider_name is not null
                then md5('rqia-provider:' || lower(service.provider_name))
        end as parent_code,
        {{ address_of(['service.address_1', 'service.address_2']) }} as address,
        service.postcode,
        nullif(upper(replace(service.postcode, ' ', '')), '') as postcode_compact,
        service.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        service.category as service_category,
        'rqia' as source,
        'other' as origin,
        'Northern Ireland' as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cast(null as date) as valid_from
    from {{ ref('stg_rqia_services') }} as service
),

hsc_hospitals as (
    select
        md5('hsc:' || upper(hospital.name) || '|' || upper(replace(hospital.postcode, ' ', ''))) as location_id,
        hospital.name,
        cast(null as varchar) as alt_name,
        cast(null as varchar) as brand_name,
        cast(null as varchar) as nhs_code,
        cast(null as varchar) as regulator,
        cast(null as varchar) as regulator_id,
        trusts.trust_name as parent_name,
        hospital.trust_code as parent_code,
        cast(null as varchar) as address,
        hospital.postcode,
        nullif(upper(replace(hospital.postcode, ' ', '')), '') as postcode_compact,
        hospital.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        'hospital' as service_category,
        'hsc' as source,
        'other' as origin,
        'Northern Ireland' as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cast(null as date) as valid_from
    from {{ ref('ni_hsc_hospitals') }} as hospital
    left join trusts
        on trusts.trust_code = hospital.trust_code
)

select * from welsh_sites
union all
select * from practices
union all
select * from hospitals
union all
select * from scottish_practices
union all
select * from care_inspectorate
union all
select * from ciw
union all
select * from rqia
union all
select * from hsc_hospitals

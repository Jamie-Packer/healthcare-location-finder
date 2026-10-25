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
        {{ address_of(['address_line_1', 'address_line_2', 'address_line_3']) }} as address
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
        {{ address_of(['address_line_1', 'address_line_2', 'address_line_3']) }} as address
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
        ods.name as alt_name,
        cqc.brand_name,
        ods.organisation_code as nhs_code,
        'CQC' as regulator,
        cqc.cqc_location_id as regulator_id,
        coalesce(orgs.name, cqc.provider_name) as parent_name,
        coalesce(ods.parent_organisation_code, cqc.provider_id) as parent_code,
        coalesce({{ address_of(['cqc.address_1', 'cqc.address_2']) }}, ods.address) as address,
        coalesce(cqc.postcode, ods.postcode) as postcode,
        coalesce(cqc.postcode_compact, ods.postcode_compact) as postcode_compact,
        coalesce(cqc.town, ods.town) as town,
        cqc.care_home,
        cqc.primary_category,
        cqc.primary_category as service_category,
        'ods+cqc' as source,
        'england' as origin,
        'England' as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cqc.region_name as cqc_region_name,
        cqc.local_authority_name as cqc_local_authority_name,
        ods.icb_code as ods_icb_code,
        coalesce(cqc.valid_from, ods.valid_from) as valid_from
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
        ods.name as alt_name,
        cast(null as varchar) as brand_name,
        ods.organisation_code as nhs_code,
        cast(null as varchar) as regulator,
        cast(null as varchar) as regulator_id,
        orgs.name as parent_name,
        ods.parent_organisation_code as parent_code,
        ods.address,
        ods.postcode,
        ods.postcode_compact,
        ods.town,
        cast(null as varchar) as care_home,
        cast(null as varchar) as primary_category,
        cast(null as varchar) as service_category,
        'ods' as source,
        'england' as origin,
        cast(null as varchar) as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cast(null as varchar) as cqc_region_name,
        cast(null as varchar) as cqc_local_authority_name,
        ods.icb_code as ods_icb_code,
        ods.valid_from
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
        cast(null as varchar) as alt_name,
        cqc.brand_name,
        cqc.ods_code as nhs_code,
        'CQC' as regulator,
        cqc.cqc_location_id as regulator_id,
        cqc.provider_name as parent_name,
        cqc.provider_id as parent_code,
        {{ address_of(['cqc.address_1', 'cqc.address_2']) }} as address,
        cqc.postcode,
        cqc.postcode_compact,
        cqc.town,
        cqc.care_home,
        cqc.primary_category,
        cqc.primary_category as service_category,
        'cqc' as source,
        'england' as origin,
        'England' as country_fallback,
        cast(null as varchar) as source_health_code,
        cast(null as varchar) as source_health_name,
        cast(null as varchar) as source_health_type,
        cqc.region_name as cqc_region_name,
        cqc.local_authority_name as cqc_local_authority_name,
        cast(null as varchar) as ods_icb_code,
        cqc.valid_from
    from current_cqc as cqc
    left join code_counts
        on cqc.ods_code = code_counts.ods_code
    where cqc.cqc_location_id not in (select regulator_id from merged)
)

select * from merged
union all
select * from ods_only
union all
select * from cqc_rest

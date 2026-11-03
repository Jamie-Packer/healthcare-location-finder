with sites as (
    select * from {{ ref('int_sites') }}
),

universe as (
    select parent_code as provider_code
    from sites
    where parent_code is not null
    union
    select organisation_code
    from {{ ref('stg_ods_trusts') }}
    where valid_to is null
    union
    select organisation_code
    from {{ ref('stg_ods_welsh_boards') }}
    where valid_to is null
    union
    select trust_code
    from {{ ref('ni_lcg_trust') }}
    union
    select health_board_code
    from {{ ref('stg_phs_council_board') }}
),

authority as (
    select
        organisation_code as provider_code,
        name,
        'ods' as code_system,
        'nhs_trust' as entity_subtype,
        'ods_etr' as name_source,
        1 as preference
    from {{ ref('stg_ods_trusts') }}
    where valid_to is null
    union all
    select
        organisation_code,
        name,
        'ods',
        'nhs_health_board',
        'ods_wlhb',
        1
    from {{ ref('stg_ods_welsh_boards') }}
    where valid_to is null
    union all
    select
        health_board_code,
        min(health_board_name),
        'phs_health_board',
        'nhs_health_board',
        'phs',
        1
    from {{ ref('stg_phs_council_board') }}
    group by health_board_code
    union all
    select
        trust_code,
        min(trust_name),
        'hsc_trust',
        'hsc_trust',
        'ni_hsc_trust_seed',
        1
    from {{ ref('ni_lcg_trust') }}
    group by trust_code
    union all
    select
        organisation_code,
        name,
        'ods',
        'independent_healthcare',
        'ods_ephp',
        2
    from {{ ref('stg_ods_independent_providers') }}
    where valid_to is null
),

authority_one as (
    select
        provider_code,
        name,
        code_system,
        entity_subtype,
        name_source
    from authority
    qualify row_number() over (
        partition by provider_code
        order by preference, name
    ) = 1
),

observed_system as (
    select
        parent_code as provider_code,
        case
            when count(*) filter (where parent_code_system = 'ods') > 0 then 'ods'
            else min(parent_code_system)
        end as code_system
    from sites
    where parent_code is not null
    group by parent_code
),

site_names as (
    select
        parent_code as provider_code,
        parent_name as name,
        count(*) as votes
    from sites
    where parent_code is not null
        and parent_name is not null
    group by 1, 2
),

mode_name as (
    select provider_code, name as mode_name
    from site_names
    qualify row_number() over (
        partition by provider_code
        order by votes desc, name asc
    ) = 1
),

cqc_names as (
    select
        provider_id as provider_code,
        case
            when count(distinct lower(sector)) = 1 then min(sector)
        end as sector
    from {{ ref('stg_cqc_locations') }}
    where provider_id is not null
        and coalesce(dormant, 'N') <> 'Y'
    group by provider_id
),

cqc_casing as (
    select
        authority_one.provider_code,
        min(cqc.provider_name) as cqc_name
    from authority_one
    inner join {{ ref('stg_cqc_locations') }} as cqc
        on cqc.provider_id = authority_one.provider_code
        and upper(cqc.provider_name) = upper(authority_one.name)
        and coalesce(cqc.dormant, 'N') <> 'Y'
    where cqc.provider_name is not null
    group by authority_one.provider_code
),

ciw_types as (
    select
        provider_urn as provider_code,
        case
            when count(distinct lower(provider_type)) = 1 then min(provider_type)
        end as provider_type
    from {{ ref('stg_ciw_services') }}
    where provider_urn is not null
    group by provider_urn
),

site_counts as (
    select parent_code as provider_code, count(*) as site_count
    from sites
    where parent_code is not null
    group by 1
),

resolved as (
    select
        universe.provider_code,
        coalesce(cqc_casing.cqc_name, authority_one.name, mode_name.mode_name) as provider_name,
        case
            when cqc_casing.cqc_name is not null then 'cqc'
            when authority_one.name is not null then authority_one.name_source
            else 'site_names'
        end as name_source,
        coalesce(authority_one.code_system, observed_system.code_system, 'unknown') as code_system,
        case
            when authority_one.entity_subtype is not null then authority_one.entity_subtype
            when cqc_map.entity_subtype is not null then cqc_map.entity_subtype
            when ciw_map.entity_subtype is not null then ciw_map.entity_subtype
            else 'unknown'
        end as entity_subtype,
        case
            when authority_one.entity_subtype is not null then authority_one.name_source
            when cqc_map.entity_subtype is not null then 'cqc'
            when ciw_map.entity_subtype is not null then 'ciw'
            else null
        end as entity_subtype_source,
        case
            when coalesce(authority_one.code_system, observed_system.code_system) = 'rqia_provider' then 'derived'
            when coalesce(authority_one.code_system, observed_system.code_system) = 'hsc_trust' then 'manually_maintained'
            else 'source_assigned'
        end as identifier_origin,
        coalesce(site_counts.site_count, 0) as site_count,
        authority_one.name as authority_name
    from universe
    left join authority_one
        on authority_one.provider_code = universe.provider_code
    left join observed_system
        on observed_system.provider_code = universe.provider_code
    left join mode_name
        on mode_name.provider_code = universe.provider_code
    left join cqc_casing
        on cqc_casing.provider_code = universe.provider_code
    left join cqc_names
        on cqc_names.provider_code = universe.provider_code
    left join {{ ref('provider_subtype_map') }} as cqc_map
        on cqc_map.source = 'cqc'
        and lower(cqc_map.category) = lower(cqc_names.sector)
    left join ciw_types
        on ciw_types.provider_code = universe.provider_code
    left join {{ ref('provider_subtype_map') }} as ciw_map
        on ciw_map.source = 'ciw'
        and lower(ciw_map.category) = lower(ciw_types.provider_type)
    left join site_counts
        on site_counts.provider_code = universe.provider_code
)

select
    provider_code,
    provider_name,
    name_source,
    code_system,
    entity_subtype,
    entity_subtype_source,
    identifier_origin,
    site_count,
    authority_name
from resolved
where provider_name is not null
    and (
        site_count > 0
        or entity_subtype in ('nhs_trust', 'nhs_health_board', 'hsc_trust')
    )
qualify row_number() over (
    partition by provider_code
    order by provider_name, entity_subtype, code_system
) = 1

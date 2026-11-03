with sites as (
    select * from {{ ref('int_sites') }}
),

providers as (
    select * from {{ ref('int_providers') }}
),

raw as (
    select
        'site:' || location_id as entity_id,
        name as alias_text,
        'preferred' as alias_type,
        true as is_preferred,
        source,
        coalesce(nhs_code, regulator_id, seed_key) as source_record_key
    from sites
    where name is not null

    union all

    select
        'site:' || location_id,
        known_as,
        'known_as',
        false,
        source,
        coalesce(nhs_code, regulator_id, seed_key)
    from sites
    where known_as is not null
        and known_as <> name

    union all

    select
        'site:' || location_id,
        address_name,
        'address_name',
        false,
        source,
        coalesce(nhs_code, regulator_id, seed_key)
    from sites
    where address_name is not null
        and address_name <> name

    union all

    select
        'site:' || location_id,
        brand_name,
        'brand',
        false,
        source,
        coalesce(nhs_code, regulator_id, seed_key)
    from sites
    where brand_name is not null

    union all

    select
        'site:' || location_id,
        alt_name,
        case
            when source in ('ods', 'ods+cqc') then 'ods_name'
            else 'alternative'
        end,
        false,
        source,
        coalesce(nhs_code, regulator_id, seed_key)
    from sites
    where alt_name is not null
        and known_as is null
        and address_name is null
        and alt_name <> name

    union all

    select
        'provider:' || provider_code,
        provider_name,
        'preferred',
        true,
        name_source,
        provider_code
    from providers

    union all

    select
        'provider:' || sites.parent_code,
        sites.parent_name,
        'alternative',
        false,
        sites.source,
        sites.parent_code
    from sites
    inner join providers
        on providers.provider_code = sites.parent_code
    where sites.parent_name is not null
        and sites.parent_name <> providers.provider_name
    group by sites.parent_code, sites.parent_name, sites.source

    union all

    select
        'provider:' || provider_code,
        authority_name,
        'alternative',
        false,
        entity_subtype_source,
        provider_code
    from providers
    where authority_name is not null
        and authority_name <> provider_name

    union all

    select
        entity_id,
        name,
        'preferred',
        true,
        case when entity_type = 'postcode' then 'site_record' else 'ons' end,
        code
    from {{ ref('search_entity') }}
    where entity_type not in ('site', 'provider')
),

labelled as (
    select
        entity_id,
        alias_text,
        {{ normalise_name('alias_text') }} as alias_normalised,
        alias_type,
        is_preferred,
        source,
        source_record_key
    from raw
    where nullif(trim(alias_text), '') is not null
)

select
    md5(entity_id || '|' || alias_type || '|' || coalesce(source, '') || '|' || alias_text) as alias_id,
    entity_id,
    alias_text,
    alias_normalised,
    alias_type,
    is_preferred,
    source,
    source_record_key,
    case
        when alias_normalised is null then 'empty_after_normalisation'
        else 'ok'
    end as normalisation_status
from labelled
qualify row_number() over (
    partition by entity_id, alias_type, source, alias_text
    order by source_record_key asc nulls last
) = 1

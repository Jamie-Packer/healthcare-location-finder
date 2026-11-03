with provider_names as (
    select parent_code, parent_name
    from {{ ref('int_sites') }}
    where parent_code is not null
        and parent_name is not null
    group by 1, 2
),

provider_conflicts as (
    select
        'provider:' || names.parent_code as entity_id,
        'name' as attribute,
        list(distinct names.parent_name) as observed_values,
        providers.provider_name as chosen_value
    from provider_names as names
    inner join {{ ref('int_providers') }} as providers
        on providers.provider_code = names.parent_code
    group by names.parent_code, providers.provider_name
    having count(distinct names.parent_name) > 1
),

other_names as (
    select
        entity_id,
        list(distinct name) as observed_values
    from {{ ref('int_entities') }}
    where entity_type <> 'provider'
    group by entity_id
    having count(distinct name) > 1
)

select
    entity_id,
    attribute,
    observed_values,
    chosen_value
from provider_conflicts

union all

select
    other_names.entity_id,
    'name' as attribute,
    other_names.observed_values,
    search_entity.name as chosen_value
from other_names
inner join {{ ref('search_entity') }} as search_entity
    on search_entity.entity_id = other_names.entity_id

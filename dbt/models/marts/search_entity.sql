-- Display values are chosen before this model is read.
-- Providers already have one name. For every other entity, the name used most
-- often wins, and the lowest name breaks a tie. search_text is taken from that
-- same row, then the lowest code if several rows share the name.
with votes as (
    select entity_id, name, count(*) as votes
    from {{ ref('int_entities') }}
    group by 1, 2
),

best_name as (
    select entity_id, name
    from votes
    qualify row_number() over (
        partition by entity_id
        order by votes desc, name asc
    ) = 1
),

picked as (
    select entities.*
    from {{ ref('int_entities') }} as entities
    inner join best_name
        on best_name.entity_id = entities.entity_id
        and best_name.name = entities.name
    qualify row_number() over (
        partition by entities.entity_id
        order by entities.code asc nulls last, entities.location_id asc nulls last
    ) = 1
),

sizes as (
    select entity_id, count(location_id) as site_count
    from {{ ref('int_entities') }}
    group by 1
)

select
    picked.entity_id,
    picked.entity_type,
    picked.name,
    picked.code,
    picked.code_system,
    picked.search_text,
    picked.entity_subtype,
    picked.entity_subtype_source,
    case when picked.entity_type = 'site' then picked.location_id end as location_id,
    sizes.site_count
from picked
inner join sizes
    on sizes.entity_id = picked.entity_id

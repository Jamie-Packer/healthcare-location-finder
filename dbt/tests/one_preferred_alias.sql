select entity_id, count(*) as preferred_aliases
from {{ ref('entity_alias') }}
where is_preferred
group by entity_id
having count(*) <> 1

union all

select entities.entity_id, 0
from {{ ref('search_entity') }} as entities
left join {{ ref('entity_alias') }} as aliases
    on aliases.entity_id = entities.entity_id
    and aliases.is_preferred
where aliases.entity_id is null

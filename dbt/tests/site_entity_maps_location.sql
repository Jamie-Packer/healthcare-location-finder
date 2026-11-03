select sites.location_id
from {{ ref('location') }} as sites
left join {{ ref('search_entity') }} as entities
    on entities.entity_id = 'site:' || sites.location_id
    and entities.entity_type = 'site'
    and entities.location_id = sites.location_id
where entities.entity_id is null
    or entities.site_count <> 1

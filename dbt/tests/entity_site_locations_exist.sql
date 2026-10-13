select links.location_id
from {{ ref('entity_site') }} as links
left join {{ ref('location') }} as location
    on links.location_id = location.location_id
where location.location_id is null

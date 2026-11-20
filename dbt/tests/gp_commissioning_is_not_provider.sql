-- Northern Ireland and Scottish GP practices carry commissioning or board areas,
-- not operator links. They must appear as health_area links, not provider links.
select
    links.entity_id,
    links.location_id
from {{ ref('entity_site') }} as links
inner join {{ ref('location') }} as location
    on location.location_id = links.location_id
where links.membership_type = 'provider'
    and location.service_type = 'gp'
    and location.country_name in ('Northern Ireland', 'Scotland')

select location_id
from {{ ref('int_site_parent') }}
where valid_to is null
group by location_id
having count(*) > 1

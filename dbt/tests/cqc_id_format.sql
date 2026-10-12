select location_id, cqc_location_id
from {{ ref('location') }}
where cqc_location_id is not null
    and not regexp_full_match(cqc_location_id, '[A-Z0-9-]+')

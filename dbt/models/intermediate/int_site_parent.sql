select
    location_id,
    parent_code,
    parent_name,
    valid_from,
    valid_to
from {{ ref('int_sites') }}
where parent_code is not null

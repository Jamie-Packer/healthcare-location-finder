select distinct
    entity_id,
    location_id,
    membership_type,
    membership_source
from {{ ref('int_entities') }}
where location_id is not null
    and membership_type is not null

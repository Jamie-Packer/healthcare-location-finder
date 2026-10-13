select location_id
from {{ ref('location') }}
where match_string is null
    or trim(match_string) = ''

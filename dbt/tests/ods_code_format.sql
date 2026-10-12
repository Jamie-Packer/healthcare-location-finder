select location_id, ods_code
from {{ ref('location') }}
where ods_code is not null
    and not regexp_full_match(ods_code, '[A-Z0-9]{3,12}')

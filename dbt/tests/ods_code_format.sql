select location_id, nhs_code
from {{ ref('location') }}
where nhs_code is not null
    and not regexp_full_match(nhs_code, '[A-Z0-9]{3,12}')

select location_id, regulator_id
from {{ ref('location') }}
where regulator = 'CQC'
    and (
        regulator_id is null
        or not regexp_full_match(regulator_id, '[A-Z0-9-]+')
    )

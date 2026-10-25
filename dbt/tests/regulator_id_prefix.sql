select location_id, regulator, regulator_id
from {{ ref('location') }}
where (regulator = 'CIW' and coalesce(regulator_id, '') not like 'SIN-%')
    or (regulator = 'Care Inspectorate' and coalesce(regulator_id, '') not like 'CS%')

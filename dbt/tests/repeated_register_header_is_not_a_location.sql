select location_id, regulator_id, nhs_code
from {{ ref('location') }}
where regulator_id = 'Location ID'
    or nhs_code = 'LOCATION ODS CODE'
    or name = 'Location Name'

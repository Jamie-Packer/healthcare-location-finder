select location_id
from {{ ref('location') }}
where local_authority_name = 'Medway'
    and county_name = 'Kent'

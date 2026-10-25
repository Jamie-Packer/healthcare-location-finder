select hospital.name, hospital.postcode
from {{ ref('ni_hsc_hospitals') }} as hospital
left join {{ ref('stg_nspl_postcodes') }} as postcode
    on upper(replace(hospital.postcode, ' ', '')) = postcode.postcode_compact
where postcode.country_code is distinct from 'N92000002'

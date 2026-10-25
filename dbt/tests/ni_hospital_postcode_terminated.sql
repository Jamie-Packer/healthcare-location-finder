{{ config(severity='warn') }}

select hospital.name, hospital.postcode
from {{ ref('ni_hsc_hospitals') }} as hospital
inner join {{ ref('stg_nspl_postcodes') }} as postcode
    on upper(replace(hospital.postcode, ' ', '')) = postcode.postcode_compact
where postcode.terminated

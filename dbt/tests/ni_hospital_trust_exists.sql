select hospital.name, hospital.trust_code
from {{ ref('ni_hsc_hospitals') }} as hospital
left join {{ ref('stg_ods_ni_orgs') }} as organisation
    on organisation.organisation_code = hospital.trust_code
    and organisation.valid_to is null
where organisation.organisation_code is null

select
    postcode_compact,
    country_code,
    region_code,
    county_code,
    local_authority_code,
    icb_code,
    sicbl_code,
    case
        when lower(cast(terminated as varchar)) in ('true', 't', '1') then true
        else false
    end as terminated
from {{ read_postcodes() }}
where postcode_compact is not null
  and postcode_compact <> ''

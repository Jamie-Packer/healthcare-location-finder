select
    postcode_compact,
    country_code,
    region_code,
    county_code,
    local_authority_code,
    icb_code
from {{ read_postcodes() }}
where postcode_compact is not null
  and postcode_compact <> ''

with sites as (
    select * from {{ ref('location') }}
)

select distinct entity_id, location_id
from (
    select 'country:' || country_name as entity_id, location_id
    from sites
    where country_name is not null
    union all
    select 'region:' || region_code, location_id
    from sites
    where region_code is not null and region_name is not null
    union all
    select 'county:' || county_code, location_id
    from sites
    where county_code is not null and county_name is not null
    union all
    select 'local_authority:' || local_authority_code, location_id
    from sites
    where local_authority_code is not null and local_authority_name is not null
    union all
    select 'icb:' || icb_code, location_id
    from sites
    where icb_code is not null and icb_name is not null
    union all
    select 'postcode:' || postcode_compact, location_id
    from sites
    where postcode_compact is not null
    union all
    select 'provider:' || parent_code, location_id
    from sites
    where parent_code is not null and parent_name is not null
    union all
    select 'site:' || location_id, location_id
    from sites
    where name is not null
) links

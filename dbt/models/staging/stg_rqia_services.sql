with source as (
    select * from {{ read_header_csv('rqia/services.csv') }}
)

select
    nullif(trim(service_id), '') as service_id,
    nullif(trim(name), '') as name,
    nullif(trim(address_1), '') as address_1,
    nullif(trim(address_2), '') as address_2,
    nullif(trim(town), '') as town,
    {{ postcode_display('postcode') }} as postcode,
    nullif(trim(category), '') as category,
    nullif(trim(provider_name), '') as provider_name
from source
where nullif(trim(service_id), '') is not null

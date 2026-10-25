with source as (
    select * from {{ read_header_csv('ciw/services.csv') }}
)

select
    nullif(trim(service_urn), '') as service_urn,
    nullif(trim(name), '') as name,
    nullif(trim(known_as), '') as known_as,
    nullif(trim(service_type), '') as service_type,
    nullif(trim(service_subtype), '') as service_subtype,
    nullif(trim(address_1), '') as address_1,
    nullif(trim(address_2), '') as address_2,
    nullif(trim(address_3), '') as address_3,
    nullif(trim(town), '') as town,
    {{ postcode_display('postcode') }} as postcode,
    nullif(trim(local_authority), '') as local_authority,
    nullif(trim(provider_urn), '') as provider_urn,
    nullif(trim(provider_name), '') as provider_name,
    nullif(trim(company_number), '') as company_number,
    nullif(trim(charity_number), '') as charity_number
from source
where nullif(trim(service_urn), '') is not null
  and (
      service_type <> 'Care Home Service'
      or service_subtype in ('Adults With Nursing', 'Adults Without Nursing')
  )

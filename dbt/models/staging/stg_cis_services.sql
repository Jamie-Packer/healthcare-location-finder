with source as (
    select * from {{ read_header_csv('care_inspectorate/services.csv') }}
)

select
    nullif(trim(service_id), '') as service_id,
    nullif(trim(name), '') as name,
    nullif(trim(service_type), '') as service_type,
    nullif(trim(service_subtype), '') as service_subtype,
    nullif(trim(address_1), '') as address_1,
    nullif(trim(address_2), '') as address_2,
    nullif(trim(address_3), '') as address_3,
    nullif(trim(town), '') as town,
    {{ postcode_display('postcode') }} as postcode,
    nullif(trim(provider_id), '') as provider_id,
    nullif(trim(provider_name), '') as provider_name,
    coalesce(
        try_strptime(nullif(trim(registered_on), ''), '%d/%m/%Y'),
        try_strptime(nullif(trim(registered_on), ''), '%Y-%m-%d')
    )::date as valid_from,
    nullif(trim(health_board_name), '') as health_board_name
from source
where nullif(trim(service_id), '') is not null
  and (
      service_type <> 'Care Home Service'
      or service_subtype in (
          'Older People',
          'Learning Disabilities',
          'Mental Health Problems',
          'Physical and Sensory Impairment',
          'Alcohol and Drugs Rehabilitation',
          'Respite Care and Short Breaks',
          'Blood Borne Virus'
      )
  )

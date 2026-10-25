-- The last address line is the town, after a trailing county. A first line that repeats the name is dropped.
with source as (
    select * from {{ read_header_csv('phs/hospitals.csv') }}
),

lined as (
    select
        nullif(upper(trim(hospital_code)), '') as hospital_code,
        nullif(trim(name), '') as name,
        list_filter(
            [
                case when upper(trim(address_1)) <> upper(trim(name)) then nullif(trim(address_1), '') end,
                nullif(trim(address_2), ''),
                nullif(trim(address_3), ''),
                nullif(trim(address_4), '')
            ],
            line -> line is not null
        ) as raw_lines,
        {{ postcode_display('postcode') }} as postcode,
        nullif(upper(trim(health_board_code)), '') as health_board_code,
        nullif(upper(trim(council_code)), '') as council_code
    from source
    where nullif(trim(hospital_code), '') is not null
),

placed as (
    select *, {{ without_county('raw_lines') }} as lines
    from lined
)

select
    hospital_code,
    name,
    {{ address_and_town('lines') }},
    postcode,
    health_board_code,
    council_code
from placed

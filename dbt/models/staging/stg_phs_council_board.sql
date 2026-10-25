with source as (
    select * from {{ read_header_csv('phs/council_board.csv') }}
)

select
    nullif(upper(trim(council_code)), '') as council_code,
    nullif(trim(council_name), '') as council_name,
    nullif(upper(trim(health_board_code)), '') as health_board_code,
    nullif(trim(health_board_name), '') as health_board_name
from source
where nullif(trim(council_code), '') is not null
  and nullif(trim(health_board_code), '') is not null
qualify row_number() over (
    partition by upper(trim(council_code))
    order by upper(trim(health_board_code))
) = 1

with countries as (
    select
        nullif(trim(CTRY25CD), '') as code,
        nullif(trim(CTRY25NM), '') as name
    from {{ read_header_csv('ons/names/CTRY.csv') }}
),
regions as (
    select
        nullif(trim(RGN25CD), '') as code,
        nullif(trim(RGN25NM), '') as name
    from {{ read_header_csv('ons/names/RGN.csv') }}
),
counties as (
    select
        nullif(trim(CTY25CD), '') as code,
        nullif(trim(CTY25NM), '') as name
    from {{ read_header_csv('ons/names/CTY.csv') }}
),
local_authorities as (
    select
        nullif(trim(LAD25CD), '') as code,
        nullif(trim(LAD25NM), '') as name
    from {{ read_header_csv('ons/names/LAD.csv') }}
),
integrated_care_boards as (
    select
        nullif(trim(ICB26CD), '') as statistical_code,
        nullif(upper(trim(ICB26CDH)), '') as ods_code,
        nullif(trim(ICB26NM), '') as name
    from {{ read_header_csv('ons/names/ICB.csv') }}
)

select
    'country' as area_type,
    code,
    cast(null as varchar) as ods_code,
    name
from countries
where code is not null and name is not null

union all

select 'region', code, null, name
from regions
where code is not null and name is not null

union all

select 'county', code, null, name
from counties
where code is not null
  and name is not null
  and name not like '(pseudo)%'
  and code not like 'E13%'
  and code not like '%99999999'

union all

select 'local_authority', code, null, name
from local_authorities
where code is not null and name is not null

union all

select 'icb', statistical_code, ods_code, name
from integrated_care_boards
where statistical_code is not null
  and name is not null
  and statistical_code not like '%99999999'

-- Welsh rows are the W-coded GP-practice role on epraccur.
-- Northern Ireland rows are the active practice file. The practice name is
-- often the first address line, and the parent code is the commissioning group.
with welsh as (
    select * from {{ read_ods('epraccur.csv') }}
),
northern_ireland as (
    select * from {{ read_ods('npraccur.csv') }}
)

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    cast(null as varchar) as alt_name,
    {{ ods_text('column04') }} as address_line_1,
    {{ ods_text('column05') }} as address_line_2,
    {{ ods_text('column06') }} as address_line_3,
    {{ ods_text('column07') }} as town,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to,
    upper({{ ods_text('column14') }}) as parent_code,
    'Wales' as nation
from welsh
where upper({{ ods_text('column00') }}) like 'W%'
    and upper({{ ods_text('column12') }}) = 'ACTIVE'
    and upper({{ ods_text('column25') }}) = 'RO76'

union all

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    {{ ods_text('column04') }} as alt_name,
    {{ ods_text('column05') }} as address_line_1,
    {{ ods_text('column06') }} as address_line_2,
    cast(null as varchar) as address_line_3,
    {{ ods_text('column07') }} as town,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to,
    upper({{ ods_text('column03') }}) as parent_code,
    'Northern Ireland' as nation
from northern_ireland
where upper({{ ods_text('column12') }}) = 'ACTIVE'

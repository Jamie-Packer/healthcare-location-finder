-- ODS etr.csv, NHS Trusts reference-data catalogue.
-- Headerless legacy layout: col 1 code, 2 name, 4 ICB code, 8 town,
-- 10 postcode, 11 legal start, 12 legal end.
with source as (
    select * from {{ read_ods('etr.csv') }}
)

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    upper({{ ods_text('column03') }}) as icb_code,
    {{ ods_text('column04') }} as address_line_1,
    {{ ods_text('column05') }} as address_line_2,
    {{ ods_text('column06') }} as address_line_3,
    {{ ods_text('column07') }} as town,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to,
    'trust' as organisation_kind
from source
where {{ ods_text('column00') }} is not null

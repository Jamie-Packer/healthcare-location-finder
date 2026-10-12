-- ODS ephp.csv, independent sector healthcare providers catalogue.
with source as (
    select * from {{ read_ods('ephp.csv') }}
)

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    upper({{ ods_text('column03') }}) as icb_code,
    {{ ods_text('column07') }} as town,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to,
    'independent_provider' as organisation_kind
from source
where {{ ods_text('column00') }} is not null

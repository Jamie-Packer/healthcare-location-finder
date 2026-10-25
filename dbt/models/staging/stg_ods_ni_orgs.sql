-- ODS niorg.csv. Trusts are parents of hospitals and practices, not sites.
with source as (
    select * from {{ read_ods('niorg.csv') }}
)

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to,
    upper({{ ods_text('column12') }}) as status,
    upper({{ ods_text('column13') }}) as role_id
from source
where {{ ods_text('column00') }} is not null

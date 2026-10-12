-- ODS ets.csv, NHS Trust Sites catalogue.
-- Col 14 is the non-primary role (RO31 marks ePACT pad-ordering codes).
-- Col 15 is the RE6 "is operated by" parent organisation code.
with source as (
    select * from {{ read_ods('ets.csv') }}
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
    {{ ods_text('column13') }} as role_id,
    upper({{ ods_text('column14') }}) as parent_organisation_code,
    'trust_site' as site_kind
from source
where {{ ods_text('column00') }} is not null

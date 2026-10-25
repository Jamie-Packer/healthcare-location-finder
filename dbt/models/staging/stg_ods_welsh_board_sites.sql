-- ODS wlhbsite.csv. The parent board is the first three characters of the site code.
with source as (
    select * from {{ read_ods('wlhbsite.csv') }}
)

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    {{ ods_text('column04') }} as address_line_1,
    {{ ods_text('column05') }} as address_line_2,
    {{ ods_text('column06') }} as address_line_3,
    {{ ods_text('column07') }} as town,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to,
    left(upper({{ ods_text('column00') }}), 3) as parent_organisation_code
from source
where {{ ods_text('column00') }} is not null
  and length(upper({{ ods_text('column00') }})) > 3

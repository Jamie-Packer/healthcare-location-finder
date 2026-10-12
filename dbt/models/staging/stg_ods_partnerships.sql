-- ODS eother.csv, strategic partnerships including integrated care boards.
-- The predefined CSV does not publish the RO318 role id. Open records whose
-- name contains "integrated care board" are the ICB list.
with source as (
    select * from {{ read_ods('eother.csv') }}
)

select
    upper({{ ods_text('column00') }}) as organisation_code,
    {{ ods_text('column01') }} as name,
    {{ ods_text('column09') }} as postcode,
    {{ ods_date('column10') }} as valid_from,
    {{ ods_date('column11') }} as valid_to
from source
where {{ ods_text('column00') }} is not null

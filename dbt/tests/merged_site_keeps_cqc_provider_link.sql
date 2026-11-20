{{ config(enabled=var('fixtures', false)) }}

-- RX1 merges ODS parent RXX with CQC provider 1-200. Both providers must link to it.
select expected.entity_id
from (values ('provider:RXX'), ('provider:1-200')) as expected(entity_id)
anti join {{ ref('entity_site') }} as links
    on links.entity_id = expected.entity_id
    and links.location_id = md5('ods:RX1')
    and links.membership_type = 'provider'

{% snapshot snap_location %}

{{
    config(
        target_schema='main',
        unique_key='location_id',
        strategy='check',
        check_cols=['name', 'parent_name', 'postcode', 'ods_code']
    )
}}

select
    location_id,
    name,
    parent_name,
    postcode,
    ods_code
from {{ ref('location') }}

{% endsnapshot %}

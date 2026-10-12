{% snapshot snap_location %}

{{
    config(
        target_schema='main',
        unique_key='location_id',
        strategy='check',
        check_cols=['name', 'parent_name']
    )
}}

select
    location_id,
    name,
    parent_name
from {{ ref('location') }}

{% endsnapshot %}

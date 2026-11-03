select location_id, seed_key
from {{ ref('int_sites') }}
where source = 'hsc'
    and (
        seed_key is null
        or location_id <> md5('hsc:' || seed_key)
        or location_id_basis <> 'hsc_seed'
    )

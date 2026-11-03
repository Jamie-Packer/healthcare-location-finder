select entity_id, entity_subtype, entity_subtype_source
from {{ ref('search_entity') }}
where entity_type = 'provider'
    and (
        (entity_subtype = 'unknown' and entity_subtype_source is not null)
        or (
            entity_subtype is not null
            and entity_subtype <> 'unknown'
            and entity_subtype_source is null
        )
    )

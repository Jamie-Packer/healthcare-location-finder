-- Every advertised (code_system, code) on search_entity must exist in entity_identifier.
select
    entity.entity_id,
    entity.code_system,
    entity.code
from {{ ref('search_entity') }} as entity
anti join {{ ref('entity_identifier') }} as identifier
    on identifier.entity_id = entity.entity_id
    and identifier.identifier_system = entity.code_system
    and identifier.identifier_value = entity.code
where entity.code is not null
    and entity.code_system is not null

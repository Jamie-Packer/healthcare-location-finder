{{ config(enabled=var('fixtures', false)) }}

select 'provider:SP2000000001' as entity_id
where (
    select count(*)
    from {{ ref('search_entity') }}
    where entity_id = 'provider:SP2000000001'
        and entity_subtype = 'unknown'
        and entity_subtype_source is null
) <> 1

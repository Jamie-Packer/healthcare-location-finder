{{ config(enabled=var('fixtures', false)) }}

select 'provider:PRN-00000000-TEST' as entity_id
where (
    select count(*)
    from {{ ref('search_entity') }}
    where entity_id = 'provider:PRN-00000000-TEST'
        and entity_subtype = 'local_authority'
        and entity_subtype_source = 'ciw'
) <> 1

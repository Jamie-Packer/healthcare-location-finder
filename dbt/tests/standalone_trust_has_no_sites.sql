{{ config(enabled=var('fixtures', false)) }}

select 'provider:RZZ' as entity_id
where (
    select count(*)
    from {{ ref('search_entity') }}
    where entity_id = 'provider:RZZ'
        and site_count = 0
        and entity_subtype = 'nhs_trust'
) <> 1

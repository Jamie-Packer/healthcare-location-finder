{{ config(enabled=var('fixtures', false)) }}

select 'provider:RXX' as entity_id
where (
    select count(*)
    from {{ ref('search_entity') }}
    where entity_id = 'provider:RXX'
        and name = 'East Example NHS Foundation Trust'
) <> 1

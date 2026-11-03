{{ config(enabled=var('fixtures', false)) }}

select 'provider subtype' as check_name
where (
    select count(*)
    from {{ ref('search_entity') }}
    where entity_id = 'provider:RXX'
        and entity_subtype = 'nhs_trust'
) <> 1
or (
    select count(*)
    from {{ ref('search_entity') }}
    where entity_id = 'provider:IND'
        and entity_subtype = 'independent_healthcare'
) <> 1

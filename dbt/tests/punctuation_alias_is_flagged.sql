{{ config(enabled=var('fixtures', false)) }}

select '***' as alias_text
where (
    select count(*)
    from {{ ref('entity_alias') }}
    where alias_text = '***'
        and alias_type = 'brand'
        and normalisation_status = 'empty_after_normalisation'
        and alias_normalised is null
) <> 1

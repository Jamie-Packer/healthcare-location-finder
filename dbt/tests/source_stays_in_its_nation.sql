with expected as (
    select * from (
        values
            ('ciw', 'Wales'),
            ('care_inspectorate', 'Scotland'),
            ('phs', 'Scotland'),
            ('rqia', 'Northern Ireland'),
            ('hsc', 'Northern Ireland'),
            ('cqc', 'England'),
            ('ods+cqc', 'England')
    ) as nations(source, country_name)
),

counts as (
    select source, country_name, count(*) as rows
    from {{ ref('location') }}
    group by 1, 2
),

totals as (
    select source, count(*) as rows
    from {{ ref('location') }}
    group by 1
)

select
    expected.source,
    expected.country_name,
    coalesce(counts.rows, 0) as rows_in_country,
    totals.rows as rows_from_source
from expected
inner join totals
    on totals.source = expected.source
left join counts
    on counts.source = expected.source
    and counts.country_name = expected.country_name
where coalesce(counts.rows, 0) * 1.0 / totals.rows < 0.90

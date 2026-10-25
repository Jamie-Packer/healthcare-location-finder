{% macro read_ods(filename) %}
read_csv(
    '{{ var("raw_root") }}/ods/{{ filename }}',
    header = false,
    all_varchar = true,
    quote = '"',
    delim = ',',
    strict_mode = false,
    null_padding = true,
    parallel = false,
    max_line_size = 1048576
)
{% endmacro %}

{% macro ods_text(column_name) %}
nullif(trim({{ column_name }}), '')
{% endmacro %}

{% macro ods_date(column_name) %}
try_strptime({{ ods_text(column_name) }}, '%Y%m%d')::date
{% endmacro %}

{% macro address_of(columns) %}
nullif(concat_ws(', ',
    {%- for column in columns %}
    nullif(trim({{ column }}), ''){% if not loop.last %},{% endif %}
    {%- endfor %}
), '')
{% endmacro %}

{% macro without_county(lines) %}
case
    when len({{ lines }}) >= 3 and regexp_matches(
        {{ lines }}[-1],
        '^((north|south|east|west|mid) |mid)?(\w+shire|\w+-shire|fife|argyll( and bute)?|lothian|angus|moray|orkney|shetland|caithness|sutherland|highland|scottish borders|western isles)$',
        'i'
    )
        then list_slice({{ lines }}, 1, len({{ lines }}) - 1)
    else {{ lines }}
end
{% endmacro %}

{% macro tidy_case(value) %}
case
    when {{ value }} = upper({{ value }})
        then array_to_string(list_transform(string_split(lower({{ value }}), ' '), lambda word: upper(word[1]) || word[2:]), ' ')
    else {{ value }}
end
{% endmacro %}

{% macro address_and_town(lines) %}
case
    when len({{ lines }}) >= 2
        then array_to_string(list_slice({{ lines }}, 1, len({{ lines }}) - 1), ', ')
    else nullif(array_to_string({{ lines }}, ', '), '')
end as address,
case when len({{ lines }}) >= 2 then {{ tidy_case(lines ~ '[-1]') }} end as town
{% endmacro %}

{% macro postcode_display(column_name) %}
case
    when nullif(trim({{ column_name }}), '') is null then null
    when trim({{ column_name }}) like '% %' then upper(trim({{ column_name }}))
    when length(replace(upper(trim({{ column_name }})), ' ', '')) between 5 and 8 then
        substring(
            replace(upper(trim({{ column_name }})), ' ', ''),
            1,
            length(replace(upper(trim({{ column_name }})), ' ', '')) - 3
        ) || ' ' || right(replace(upper(trim({{ column_name }})), ' ', ''), 3)
    else upper(trim({{ column_name }}))
end
{% endmacro %}

{% macro read_postcodes() %}
{% if var("postcodes_format", "parquet") == "csv" %}
read_csv(
    '{{ var("raw_root") }}/ons/postcodes.csv',
    header = true,
    all_varchar = true
)
{% else %}
read_parquet('{{ var("raw_root") }}/ons/postcodes.parquet')
{% endif %}
{% endmacro %}

{% macro read_header_csv(relative_path) %}
read_csv(
    '{{ var("raw_root") }}/{{ relative_path }}',
    header = true,
    all_varchar = true,
    quote = '"',
    delim = ',',
    strict_mode = false,
    null_padding = true,
    parallel = false,
    max_line_size = 2000000,
    ignore_errors = true
)
{% endmacro %}

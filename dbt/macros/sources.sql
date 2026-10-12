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

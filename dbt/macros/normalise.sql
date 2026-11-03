{# name-norm-1. Upper case, strip accents, turn & into AND, drop apostrophes,
   then turn every other non-alphanumeric run into a single space. Words are kept. #}
{% macro normalise_name(expression) %}
nullif(trim(regexp_replace(
    regexp_replace(
        replace(upper(strip_accents(cast({{ expression }} as varchar))), '&', ' AND '),
        '[''`´’‘]',
        '',
        'g'
    ),
    '[^A-Z0-9]+',
    ' ',
    'g'
)), '')
{% endmacro %}

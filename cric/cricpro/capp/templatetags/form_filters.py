from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def add_attr(field, attr_string):
    attrs = {}
    for attr in attr_string.split(","):
        key, val = attr.split("=")
        attrs[key.strip()] = val.strip()
    return field.as_widget(attrs=attrs)

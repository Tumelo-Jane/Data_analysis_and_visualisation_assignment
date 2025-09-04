


from django import template
register = template.Library()

@register.filter
def dictget(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def first(pair):
    return pair[0] if pair else ""

@register.filter
def last(pair):
    return pair[1] if pair else ""




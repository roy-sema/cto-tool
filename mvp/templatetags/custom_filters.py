import json
import logging

from django import template

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name="startswith")
def startswith(text, starts):
    if isinstance(text, str):
        starts = starts.split(",")
        return any(text.startswith(s) for s in starts)
    return False


@register.filter(name="ifinlist")
def if_in_list(value, collection_string):
    return value in collection_string.split(",")


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key) if dictionary else None


@register.tag(name="nolinebreaks")
def no_line_breaks(parser, token):
    nodelist = parser.parse(("endnolinebreaks",))
    parser.delete_first_token()
    return RemoveLinebreaksNode(nodelist)


@register.filter
def json_dumps(value):
    return json.dumps(value)


class RemoveLinebreaksNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return output.replace("\n", "")


@register.filter
def add_str(arg1, arg2):
    return str(arg1) + str(arg2)

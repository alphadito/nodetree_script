import bpy
import typing
from collections import deque, Counter
from .util import level_topo_sort

def _arrange(node_tree, padding: typing.Tuple[float, float] = (50, 25)):
    graph = { node:set() for node in node_tree.nodes }
    node_input_link_count = Counter()
    for link in node_tree.links:
        graph[link.from_node].add(link.to_node)
        node_input_link_count[link.to_socket] += 1

    columns = level_topo_sort(graph)

    # Arrange the columns, computing the size of the node manually so arrangement can be done without UI being visible.
    UI_SCALE = bpy.context.preferences.view.ui_scale
    NODE_HEADER_HEIGHT = 20
    NODE_LINK_HEIGHT = 28
    NODE_PROPERTY_HEIGHT = 28
    NODE_VECTOR_HEIGHT = 84
    x = 0
    for col in columns:
        largest_width = 0
        y = 0
        for node in col:
            node.update()
            input_count = len(list(filter(lambda i: i.enabled, node.inputs)))
            output_count = len(list(filter(lambda i: i.enabled, node.outputs)))
            parent_props = [prop.identifier for base in type(node).__bases__ for prop in base.bl_rna.properties]
            properties_count = len([prop for prop in node.bl_rna.properties if prop.identifier not in parent_props])
            unset_vector_count = len(list(filter(lambda i: i.enabled and i.type == 'VECTOR' and node_input_link_count[i] == 0, node.inputs)))
            node_height = (
                NODE_HEADER_HEIGHT \
                + (output_count * NODE_LINK_HEIGHT) \
                + (properties_count * NODE_PROPERTY_HEIGHT) \
                + (input_count * NODE_LINK_HEIGHT) \
                + (unset_vector_count * NODE_VECTOR_HEIGHT)
            ) * UI_SCALE
            if node.width > largest_width:
                largest_width = node.width
            node.location = (x, y)
            y -= node_height + padding[1]
        x += largest_width + padding[0]
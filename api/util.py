import bpy
import re
from collections import deque

lower_snake_case = lambda x: re.sub(r'[ -./]', '_', x.lower())
title_case = lambda x: re.sub(r'[- _./]', '', x.title())
upper_snake_case = lambda x: ('_' if not x[0].isalpha() else '') + re.sub(r'[ -./]', '_', x.upper())

def _as_iterable(x):
    try :
        return iter(x)
    except:
        return [x]

def get_bpy_subclasses(base_bpy_type,include_base=False):
    for bpy_type_name in dir(bpy.types):
        bpy_type = getattr(bpy.types, bpy_type_name)
        if isinstance(bpy_type,type) and issubclass(bpy_type,base_bpy_type) and (include_base or bpy_type != base_bpy_type):
            yield bpy_type

def get_unique_subclass_properties(bpy_type):
    parent_props = [prop for base in bpy_type.__bases__ for prop in base.bl_rna.properties]
    for prop in bpy_type.bl_rna.properties:
        if not prop in parent_props:
            yield prop

def non_virtual_sockets(sockets):
    return [ socket for socket in sockets if type(socket) != bpy.types.NodeSocketVirtual ]

def enabled_sockets(sockets):
    for socket in sockets:
        if socket.enabled:
            yield socket

class Attrs:
    def __init__(self,**kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def topo_sort(graph):
    in_degree = {u: 0 for u in graph}
    for u in graph:
        for v in graph[u]:
            in_degree[v] += 1
    queue = deque([u for u in in_degree if in_degree[u] == 0])
    topo_order = []
    while queue:
        u = queue.popleft()
        topo_order.append(u)
        for v in graph[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
    return topo_order

def level_topo_sort(graph):
    sorted_nodes = topo_sort(graph)
    levels = []
    level_index = {}
    for node in reversed(sorted_nodes):
        level_index[node] = max([ level_index[adj_node] for adj_node in graph[node] ], default=-1) + 1
        if level_index[node] == len(levels):
            levels.append([node])
        else:
            levels[level_index[node]].append(node)
    levels = reversed(levels)
    return levels
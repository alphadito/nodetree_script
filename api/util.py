import bpy
import re

lower_snake_case = lambda x: re.sub(r'[ -./]', '_', x.lower())
title_case = lambda x: re.sub(r'[- _./]', '', x.title())
upper_snake_case = lambda x: ('_' if not x[0].isalpha() else '') + re.sub(r'[ -./]', '_', x.upper())

def _as_iterable(x):
    return iter(x) if hasattr(x, '__iter__') else [x]

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
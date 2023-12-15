import bpy
import numpy as np
from ..noderegistrar import NodeRegistrar,upper_snake_case
from ..util import get_unique_subclass_properties, _as_iterable, title_case, lower_snake_case, enabled_sockets
from ..nodesocket import get_shortened_socket_type_name

is_math_operation_arg = lambda func_name, argname: func_name in ['math','vector_math'] and argname == 'operation'
def node_to_script(node):
    node_type = type(node)
    node_info = NodeRegistrar.all_node_info[node_type]
    func_name = node_info.func_name
    has_variable_input = node_type in [bpy.types.NodeGroupOutput,bpy.types.GeometryNodeGroup,bpy.types.ShaderNodeGroup,bpy.types.CompositorNodeGroup,bpy.types.TextureNodeGroup]
    args=[]
    for prop in get_unique_subclass_properties(node_info.type):
        typename = f"{node_info.namespace}.{title_case(prop.identifier)}" if prop.type == 'ENUM'  else prop.type.title()
        argname = lower_snake_case(prop.identifier)
        value = getattr(node,prop.identifier)
        if prop.type == 'POINTER':
            continue

        if is_math_operation_arg(node_info.func_name,argname):
            func_name = NodeRegistrar.math_aliases.get(lower_snake_case(value),lower_snake_case(value))
            continue

        default_value = None if has_variable_input else node_info.default_value[argname][typename][0]

        if value != default_value:
            if prop.type == 'ENUM':
                args.append(f'{argname}={typename}.{upper_snake_case(value)}')
            else:
                args.append(f'{argname}={repr(value)}')

    for node_input in enabled_sockets(node.inputs):
        typename = get_shortened_socket_type_name(node_input)
        argname = lower_snake_case(node_input.name)
        value = getattr(node_input,'default_value',None)
        default_value = None if has_variable_input else node_info.default_value[argname][typename][0]
        if node_input.type in ['VALUE','INT','VECTOR','RGBA','ROTATION']:
            value = tuple(_as_iterable(value))
            is_default_value = False if has_variable_input else np.mean( np.abs( np.array( value  ) - np.array( default_value  ) ) ) < 1e-6
            value = value if len(value) > 1 else value[0]
        else:
            is_default_value = value == default_value
            value = repr(value)

        if not is_default_value:
            args.append(f'{argname}={value}')

    script = func_name+'(' + ','.join(args) + ')'
    return script
import bpy
import numpy as np
from ..api.noderegistrar import NodeRegistrar,upper_snake_case
from ..api.util import get_unique_subclass_properties, _as_iterable, title_case, lower_snake_case, enabled_sockets, Attrs, topo_sort
from ..api.nodesocket import get_shortened_socket_type_name
from collections import Counter, defaultdict
from mathutils import Vector


is_math_operation_arg = lambda func_name, argname: func_name in ['math','vector_math'] and argname == 'operation'
is_math_vector_or_value_arg = lambda func_name, argname: func_name in ['math','vector_math'] and argname in ['vector','value']
def node_to_script(node):
    node_type = type(node)
    node_info = NodeRegistrar.all_node_info[node_type]
    func_name = node_info.func_name
    has_variable_input = node_type in [bpy.types.NodeGroupOutput,bpy.types.GeometryNodeGroup,bpy.types.ShaderNodeGroup,bpy.types.CompositorNodeGroup,bpy.types.TextureNodeGroup]
    args=defaultdict(list)

    for prop in get_unique_subclass_properties(node_info.type):
        typename = f"{node_info.namespace}.{title_case(prop.identifier)}" if prop.type == 'ENUM'  else prop.type.title()
        argname = lower_snake_case(prop.identifier)
        value = getattr(node,prop.identifier)

        default_value = None if has_variable_input else node_info.default_value[argname][typename][0]
        if type(value) == Vector:
            value = tuple(value)
        if prop.type == 'POINTER':
            continue

        is_default_value = value == default_value
        if not is_default_value or is_math_operation_arg(node_info.func_name,argname):
            if prop.type == 'ENUM':
                args[argname].append(f'{typename}.{upper_snake_case(value)}')
            else:
                args[argname].append(repr(value))

    for node_input in enabled_sockets(node.inputs):
        argname = lower_snake_case(node_input.name)
        typename = get_shortened_socket_type_name(type(node_input))
        if node_input.is_multi_input:
            typename = f"List[{typename}]"
            args[argname].append([])
            continue
        value = getattr(node_input,'default_value',None)
        default_value = None if has_variable_input else node_info.default_value[argname][typename][0]
        if node_input.type in ['VALUE','INT','VECTOR','RGBA','ROTATION']:
            value = tuple(_as_iterable(value))
            is_default_value = False if has_variable_input else np.mean( np.abs( np.array( value  ) - np.array( default_value  ) ) ) < 1e-6
            value = value if len(value) > 1 else value[0]
        else:
            is_default_value = value == default_value
            value = repr(value)

        if not is_default_value or node_input.is_linked or len(node_info.default_value[argname][typename]) > 1 or is_math_vector_or_value_arg(func_name,argname):
            args[argname].append(value)

    script_info = Attrs(func_name=func_name,args=args)

    return script_info


def nodes_to_script(nodes):
    if len(nodes) == 0:
        return ''
    node_tree = nodes[0].id_data

    graph = { node:set() for node in nodes }
    links = []
    for link in node_tree.links:
        if link.from_node in graph and link.to_node in graph:
            graph[link.from_node].add(link.to_node)
            links.append(link)
    sorted_nodes = topo_sort(graph)

    symbol_count = Counter()
    script_info={}
    for node in sorted_nodes:
        script_info[node]=node_to_script(node)
        symbol_count[script_info[node].func_name]+=1
        script_info[node].symbol = f'{script_info[node].func_name}{symbol_count[script_info[node].func_name]}'

    for link in links:
        from_symbol = script_info[link.from_node].symbol
        if len( list(enabled_sockets(link.from_node.outputs)) ) > 1:
            from_symbol += f".{lower_snake_case(link.from_socket.name)}"
        input_index = NodeRegistrar.all_node_info[type(link.to_node)].input_index[link.to_socket.identifier]
        if link.to_socket.is_multi_input:
            script_info[link.to_node].args[lower_snake_case(link.to_socket.name)][input_index].append(from_symbol)
        else:
            script_info[link.to_node].args[lower_snake_case(link.to_socket.name)][input_index] = from_symbol

    script_lines = []
    for node in sorted_nodes:
        symbol = script_info[node].symbol
        func_name = script_info[node].func_name
        func_args = []
        alt_func_name = None
        no_args_node = type(node) in [bpy.types.ShaderNodeValue,bpy.types.ShaderNodeRGB,bpy.types.CompositorNodeValue]
        if no_args_node:
            value = node.outputs[0].default_value
            value = tuple(_as_iterable(value))
            if len(value) == 1:
                value = value[0]
            script_line = f"{symbol} = State.NodeSocket.create({value})"
            script_lines.append(script_line)
            continue
        for arg, vals in script_info[node].args.items():
            if is_math_operation_arg(func_name,arg):
                operation = vals[0].split('.')[-1]
                alt_func_name = NodeRegistrar.math_aliases.get(lower_snake_case(operation),lower_snake_case(operation))
                continue
            if is_math_vector_or_value_arg(func_name,arg):
                arg_str = str(vals).replace("'","")[1:-1]
                func_args.append(arg_str)
                continue

            val = vals[0] if len(vals) == 1 else vals
            val = str(val).replace("'","")

            arg_str = f"{arg}={val}"
            func_args.append(arg_str)

        if alt_func_name:
            func_name = alt_func_name
        func_call = f"{func_name}({','.join(func_args)})"

        script_line = f"{symbol} = {func_call}"
        script_lines.append(script_line)
    script = '\n'.join(script_lines)

    return script
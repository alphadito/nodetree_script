import bpy
import numpy as np
from ..api.noderegistrar import NodeRegistrar,upper_snake_case
from ..api.util import get_unique_subclass_properties, _as_iterable, title_case, lower_snake_case, enabled_sockets, Attrs, level_topo_sort
from ..api.nodesocket import get_shortened_socket_type_name
from ..api.nodetree import NodeTree
from collections import Counter, defaultdict
import mathutils


node_groups = [bpy.types.GeometryNodeGroup,bpy.types.ShaderNodeGroup,bpy.types.CompositorNodeGroup,bpy.types.TextureNodeGroup]
is_math_operation_arg = lambda func_name, argname: func_name in ['math','vector_math'] and argname == 'operation'
is_math_vector_or_value_arg = lambda func_name, argname: func_name in ['math','vector_math'] and argname in ['vector','value']
is_node_tree_input_arg = lambda node_type, argname: node_type in node_groups and argname == 'node_tree'
is_curve_mapping_arg = lambda value: type(value) == bpy.types.CurveMapping

def node_to_script(node):
    node_type = type(node)
    node_info = NodeRegistrar.all_node_info[node_type]
    func_name = node_info.func_name
    args=defaultdict(list)

    for prop in get_unique_subclass_properties(node_info.type):
        typename = f"{node_info.namespace}.{title_case(prop.identifier)}" if prop.type == 'ENUM'  else prop.type.title()
        argname = lower_snake_case(prop.identifier)
        value = getattr(node,prop.identifier)

        if len(node_info.default_value[argname][typename]) > 0:
            default_value = node_info.default_value[argname][typename][0]
        else:
            default_value = None

        if type(value) == mathutils.Vector:
            value = tuple(value)

        if prop.type == 'POINTER':
            if is_node_tree_input_arg(node_type,argname):
                args[argname].append(repr(value))
                continue
            elif is_curve_mapping_arg(value):
                args[argname].append(value)
                continue
            else:
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
        
        if len(node_info.default_value[argname][typename]) > 0:
            default_value = node_info.default_value[argname][typename][0]
        else:
            default_value = None
        
        if node_input.type in ['VALUE','INT','VECTOR','RGBA','ROTATION']:
            value = tuple(_as_iterable(value))
            is_default_value = False if default_value is None else np.mean( np.abs( np.array( value  ) - np.array( default_value  ) ) ) < 1e-6
            value = value if len(value) > 1 else value[0]
        else:
            is_default_value = value == default_value
            value = repr(value)

        if not is_default_value or node_input.is_linked or len(node_info.default_value[argname][typename]) > 1 or is_math_vector_or_value_arg(func_name,argname):
            args[argname].append(value)

    script_info = Attrs(func_name=func_name,args=args)

    return script_info


def nodes_to_script(nodes,make_function=False):
    outputs = []
    inputs = {}

    if len(nodes) == 0:
        return ''
    node_tree = nodes[0].id_data

    graph = { node:set() for node in nodes }
    links = []
    for link in node_tree.links:
        if link.from_node in graph and link.to_node in graph:
            graph[link.from_node].add(link.to_node)
            links.append(link)

    columns = level_topo_sort(graph)
    sorted_nodes = [node for col in columns for node in col]

    symbol_count = Counter()
    script_info={}
    for node in sorted_nodes:
        script_info[node]=node_to_script(node)
        symbol_count[script_info[node].func_name]+=1
        script_info[node].symbol = f'{script_info[node].func_name}{symbol_count[script_info[node].func_name]}'

        if type(node) == bpy.types.NodeGroupInput:
            for tree_input in NodeTree(node_tree.name).inputs:
                argname = lower_snake_case(tree_input.name)
                socket_type = tree_input.bl_socket_idname
                typename = socket_type.replace('NodeSocket','')
                enum_socket_type = NodeRegistrar.enum_socket_type.get(socket_type)
                value = getattr(tree_input,'default_value',None)
                if enum_socket_type in ['VECTOR','RGBA','ROTATION']:
                    value = tuple(_as_iterable(value))
                inputs[argname] = Attrs(socket_type=typename,default_value=value)

    for link in links:
        from_symbol = script_info[link.from_node].symbol
        if len( list(enabled_sockets(link.from_node.outputs)) ) > 1:
            from_symbol += f".{lower_snake_case(link.from_socket.name)}"

        if make_function:
            if type(link.from_node) == bpy.types.NodeGroupInput:
                from_symbol = lower_snake_case(link.from_socket.name)

        if type(link.to_node) == bpy.types.NodeGroupOutput:
            outputs.append(from_symbol)
            continue

        if type(link.to_node) in node_groups:
            input_index = 0
        else:
            input_index = NodeRegistrar.all_node_info[type(link.to_node)].input_index[link.to_socket.identifier]

        if link.to_socket.is_multi_input:
            script_info[link.to_node].args[lower_snake_case(link.to_socket.name)][input_index].append(from_symbol)
        else:
            script_info[link.to_node].args[lower_snake_case(link.to_socket.name)][input_index] = from_symbol

    script_lines = []
    for node in sorted_nodes:
        if type(node) == bpy.types.NodeGroupOutput:
            continue

        if make_function:
            if type(node) == bpy.types.NodeGroupInput:
                continue

        symbol = script_info[node].symbol
        func_name = script_info[node].func_name
        func_args = []
        alt_func_name = None
        no_args_input_node = type(node) in [bpy.types.ShaderNodeValue,bpy.types.ShaderNodeRGB,bpy.types.CompositorNodeValue]


        if no_args_input_node:
            data_path = f'nodes["{node.name}"].outputs[0].default_value'
            fcurve = node_tree.animation_data.drivers.find(data_path) if node_tree.animation_data else None
            if fcurve:
                func_call = f"scripted_expression('{fcurve.driver.expression}')"
            else:
                value = node.outputs[0].default_value
                value = tuple(_as_iterable(value))
                if len(value) == 1:
                    value = value[0]
                func_call = f"State.NodeSocket.create({value})"

            script_line = f"{symbol} = {func_call}"
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

            if is_curve_mapping_arg(vals[0]):
                curves = str([ "Curve([" + ','.join( f"Point({p.location[0]},{p.location[1]})" for p in curve.points) + "])" for curve in vals[0].curves]).replace("'","")
                if len(vals[0].curves) == 1:
                    curves = curves[1:-1]
                script_line = f"{symbol}_mapping = {curves}"
                script_lines.append(script_line)
                arg_str = f"{arg}={symbol}_mapping"
                func_args.append(arg_str)
                continue

            val = vals[0] if len(vals) == 1 else vals

            arg_str = f"{arg}={val}"
            if type(val) == list:
                arg_str = arg_str.replace("'","")
            func_args.append(arg_str)

        if alt_func_name:
            func_name = alt_func_name
        func_call = f"{func_name}({','.join(func_args)})"

        script_line = f"{symbol} = {func_call}"
        script_lines.append(script_line)

    delim = '\n    ' if make_function else '\n'
    script = delim.join(script_lines)

    if make_function:
        default_value_str = lambda val: f' = {repr(val.default_value)}' if val.default_value is not None else ''
        function_def_script_line = f"def {node_tree.name}_copy({', '.join([f'{arg}: {val.socket_type}{default_value_str(val)}' for arg, val in inputs.items()])}):"
        return_script_line = f"    return {', '.join(outputs)}"
        script = '\n'.join([f"@{node_tree.type.lower()}tree",function_def_script_line,'    '+script,return_script_line])
    return script


class CopySelectedNodes(bpy.types.Operator):
    """Copy Selected Nodes to Clipboard"""
    bl_idname = "node.copy_selected"
    bl_label = "Copy Selected Nodes as Script"

    def execute(self, context):
        if context.space_data.type == 'NODE_EDITOR' and context.space_data.node_tree:
            node_tree = context.space_data.path[-1].node_tree
            selected_nodes = [node for node in node_tree.nodes if node.select]
            script = nodes_to_script(selected_nodes)
            bpy.context.window_manager.clipboard = script
            self.report({'INFO'}, f"{len(selected_nodes)} nodes copied to clipboard.")

        return {'FINISHED'}


class CopyNodeTree(bpy.types.Operator):
    """Copy NodeTree to Clipboard"""
    bl_idname = "node.copy_node_tree"
    bl_label = "Copy NodeTree as Script"

    def execute(self, context):
        if context.space_data.type == 'NODE_EDITOR' and context.space_data.node_tree:
            node_tree = context.space_data.path[-1].node_tree
            selected_nodes = [node for node in node_tree.nodes]
            script = nodes_to_script(selected_nodes,make_function=True)
            bpy.context.window_manager.clipboard = script
            self.report({'INFO'}, f"{len(selected_nodes)} nodes copied to clipboard.")

        return {'FINISHED'}
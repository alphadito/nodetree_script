import bpy
import inspect
import typing
from functools import partial
from ..state import State
from ..node import NodeOutputs, set_or_create_link
from ..nodetree import InputInfo
from ..util import _as_iterable, non_virtual_sockets

def non_virtual_sockets(sockets):
    return [ socket for socket in sockets if type(socket) != bpy.types.NodeSocketVirtual ]

def socket_type_to_data_type(socket_type):
    match socket_type:
        case 'NodeSocketBool':
            return 'BOOLEAN'
        case 'NodeSocketColor':
            return 'RGBA'
        case _:
            return socket_type.replace('NodeSocket', '').upper()

def zone(block: typing.Callable,zone_input_node_type,zone_output_node_type,zone_out_items_attribute):
    def wrapped(*args, **kwargs):
        zone_in = State.current_node_tree.new_node(zone_input_node_type.__name__)
        zone_out = State.current_node_tree.new_node(zone_output_node_type.__name__)
        zone_in.pair_with_output(zone_out)
        zone_out_items = getattr(zone_out,zone_out_items_attribute)
        for item in zone_out_items:
            zone_out_items.remove(item)


        zone_items = {}
        param_skip = len(non_virtual_sockets(zone_in.outputs))
        signature = inspect.signature(block)
        for i, param in enumerate( list(signature.parameters.values())[param_skip:] ):
            zone_items[param.name] = InputInfo(param.name ,param.annotation.socket_type, param.default, i)
        for param_name,input_info in zone_items.items():
            zone_out_items.new(socket_type_to_data_type(input_info.socket_type), input_info.name)
            set_or_create_link(kwargs.get(param_name,args[input_info.index]), zone_in.inputs[input_info.index])


        step = block(*[State.NodeSocket.create(o) for o in non_virtual_sockets(zone_in.outputs)])
        for i, result in enumerate(_as_iterable(step)):
            set_or_create_link(result, zone_out.inputs[i])
        outputs = NodeOutputs({socket.name: socket for socket in non_virtual_sockets(zone_out.outputs)})
        if len(outputs) == 1:
            return outputs[0]
        else:
            return outputs

    return wrapped

version = bpy.app.version

if version >= (3,6,0):
    simulation_zone = partial(zone,zone_input_node_type=bpy.types.GeometryNodeSimulationInput,zone_output_node_type=bpy.types.GeometryNodeSimulationOutput,zone_out_items_attribute='state_items')
    """
        Create a simulation input/output block.

        In Blender 4.0+, you must return a boolean value for the "Skip" argument as the first element in the return tuple.

        > Only available in Blender 3.6+.
    """
else:
    def simulation_zone(block):
        raise Exception("Simulation Zone is only available in Blender 3.6+")

if version >= (4,0,0):
    repeat_zone =  partial(zone,zone_input_node_type=bpy.types.GeometryNodeRepeatInput,zone_output_node_type=bpy.types.GeometryNodeRepeatOutput,zone_out_items_attribute='repeat_items')
    """
        Create a repeat input/output block.

        > Only available in Blender 4.0+.
    """
else:
    def repeat_zone(block):
        raise Exception("Repeat Zone is only available in Blender 4.0+")
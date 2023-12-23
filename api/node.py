from collections import defaultdict
import enum
from .state import State
from .static.curve import Curve
from .util import lower_snake_case, get_unique_subclass_properties, _as_iterable, enabled_sockets

class NodeOutputs(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dict_copy = list(self.items())
        self.clear()
        for key,value in dict_copy:
            self[key] = value
    @classmethod
    def create(cls, value):
        if isinstance(value, cls):
            return value
        elif isinstance(value, dict):
            outputs = value
        elif isinstance(value, State.NodeSocket):
            outputs = {value._socket.name:value}
        elif value is None:
            outputs = {}
        else:
            outputs = { f'Result{i}':output for i,output in enumerate(_as_iterable(value)) }

        return cls(outputs)

    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else  super().__getitem__(key)
    def __iter__(self):
        return iter(self.values())
    def __setitem__(self,key,value):
        key = lower_snake_case(key)
        value = State.NodeSocket.create(value)
        super().__setitem__(key, value)
    def __setattr__(self,name,value):
        self[name] = value

    __getattr__ = dict.get
    __delattr__ = dict.__delitem__

def set_or_create_link(value,node_input):
    try:
        node_input.default_value = value
    except:
        State.current_node_tree.link(State.NodeSocket.create(value)._socket, node_input)

class Node:
    def __init__(self,node_type):
        self._node = State.current_node_tree.new_node(node_type.__name__)
        self.type = type(self._node)

    @staticmethod
    def build_node(primary_arg=None,node_type=None,get_socket_if_singular_output=True,return_node=False,**kwargs):
        node = Node(node_type)
        if primary_arg:
            node.set_primary_arg(primary_arg)
        kwargs=node.set_properties(**kwargs)
        node.set_inputs(**kwargs)

        node.outputs = node.get_outputs()
        if return_node:
            return node
        elif len(node.outputs) == 1 and get_socket_if_singular_output:
            return node.outputs[0]
        else:
            return node.outputs

    def set_primary_arg(self,primary_arg):
        State.current_node_tree.link(primary_arg._socket, self._node.inputs[0])

    def set_properties(self,**kwargs):
        for prop in get_unique_subclass_properties(self.type):
            argname = lower_snake_case(prop.identifier)
            value = kwargs.pop(argname,None)
            if value is not None:
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], Curve):
                    for i, curve in enumerate(value):
                        curve.apply(getattr(self._node, prop.identifier).curves[i])
                    continue
                elif isinstance(value, Curve):
                    value.apply(getattr(self._node, prop.identifier).curves[0])
                    continue
                elif isinstance(value, enum.Enum):
                    value = value.value

                setattr(self._node, prop.identifier, value)
        return kwargs

    def set_inputs(self,**kwargs):
        node_input_lists = defaultdict(list)
        for node_input in enabled_sockets(self._node.inputs):
            argname = lower_snake_case(node_input.name)
            node_input_lists[argname].append(node_input)

        for argname,value in kwargs.items():
            self.validate_argname(argname,node_input_lists)
            node_input_list = node_input_lists[argname]
            values,node_input_list = self.handle_iterable_inputs(value,node_input_list)
            for value,node_input in zip(values,node_input_list):
                set_or_create_link(value,node_input)

    def validate_argname(self,argname,node_input_lists):
        if argname not in node_input_lists:
            raise Exception(f"Node {self._node.name} does not have an input named {argname}")

    def handle_iterable_inputs(self,value,node_input_list):
        if node_input_list[0].is_multi_input:
            values = value
            node_input_list = [node_input_list[0]]*len(values)
        else:
            if ( not hasattr(value, '__iter__') or len(node_input_list) == 1  ):
                values = [value]
            else:
                values = value

        return values,node_input_list

    def get_outputs(self):
        return NodeOutputs( {socket.name:socket for socket in enabled_sockets(self._node.outputs)} )

class GeometryNode(Node):
    pass
class ShaderNode(Node):
    pass
class CompositorNode(Node):
    pass
class FunctionNode(Node):
    pass
class TextureNode(Node):
    pass


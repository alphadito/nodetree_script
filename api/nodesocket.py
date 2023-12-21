import bpy
import enum
from .state import State
from .node import Node
from .static.sample_mode import SampleMode
from .util import get_bpy_subclasses


class NodeSocket:
    type_to_node = { tuple: {} }

    @classmethod
    def create(cls,value):
        if isinstance(value,cls):
            return value
        else:
            return cls(value)

    @classmethod
    @property
    def class_math(cls):
        from .dynamic.shader import math
        return math

    @classmethod
    @property
    def class_vector_math(cls):
        from .dynamic.shader import vector_math
        return vector_math

    def __init__(self, value):
        if isinstance(value,NodeSocket):
            self._socket = value._socket
        elif isinstance(value, bpy.types.NodeSocket):
            self._socket = value
        else:
            if type(value) is tuple:
                node_type, property = self.__class__.type_to_node[tuple].get(len(value),(None,None))
            else:
                node_type, property= self.__class__.type_to_node.get(type(value),(None,None) )

            if node_type is None:
                raise Exception(f"The {self.__class__.__name__} class cannot express '{value}' of type '{type(value).__name__}' as a node socket")

            node = Node(node_type)._node
            if property:
                setattr(node, property, value)
            else:
                 node.outputs[0].default_value = value

            self._socket = node.outputs[0]

        self.socket_type = type(self._socket).__name__

    def _math(self, other, operation, reverse=False):
        if other is None:
            vector_or_value = self
        else:
            vector_or_value =  (other, self) if reverse else (self, other)

        if self._socket.type in ['VECTOR','RGBA']:
            return self.__class__.class_vector_math(operation=operation, vector=vector_or_value)
        else:
            return self.__class__.class_math(operation=operation, value=vector_or_value)

    def __add__(self, other):
        return self._math(other, 'ADD')

    def __radd__(self, other):
        return self._math(other, 'ADD', True)

    def __sub__(self, other):
        return self._math(other, 'SUBTRACT')

    def __rsub__(self, other):
        return self._math(other, 'SUBTRACT', True)

    def __mul__(self, other):
        return self._math(other, 'MULTIPLY')

    def __rmul__(self, other):
        return self._math(other, 'MULTIPLY', True)

    def __truediv__(self, other):
        return self._math(other, 'DIVIDE')

    def __rtruediv__(self, other):
        return self._math(other, 'DIVIDE', True)

    def __mod__(self, other):
        return self._math(other, 'MODULO')

    def __rmod__(self, other):
        return self._math(other, 'MODULO', True)

    def __floordiv__(self, other):
        return self._math(other, 'DIVIDE')._math(None, 'FLOOR')

    def __rfloordiv__(self, other):
        return self._math(other, 'DIVIDE', True)._math(None, 'FLOOR')

    def __pow__(self, other):
        return self._math(other, 'POWER')

    def __rpow__(self, other):
        return self._math(other, 'POWER', True)

    def __matmul__(self, other):
        return self._math(other, 'DOT_PRODUCT')

    def __rmatmul__(self, other):
        return self._math(other, 'DOT_PRODUCT', True)

    def __abs__(self):
        return self._math(None, 'ABSOLUTE')

    def __neg__(self):
        return self._math(-1, 'MULTIPLY')

    def __pos__(self):
        return self

    def __round__(self):
        return self._math(None,'ROUND')

    def __invert__(self):
        return self._math((-1, -1, -1) if self._socket.type == 'VECTOR' else -1, 'MULTIPLY')

    def _get_xyz_component(self, component):
        if self._socket.type != 'VECTOR':
            raise Exception("`x`, `y`, `z` properties are not available on non-Vector types.")
        separate_node = Node(bpy.types.ShaderNodeSeparateXYZ)._node
        State.current_node_tree.link(self._socket, separate_node.inputs[0])
        return self.__class__(separate_node.outputs[component])
    @property
    def x(self):
        return self._get_xyz_component(0)
    @property
    def y(self):
        return self._get_xyz_component(1)
    @property
    def z(self):
        return self._get_xyz_component(2)
    def __getitem__(self, subscript):
        if self._socket.type == 'VECTOR' and isinstance(subscript, int):
            return self._get_xyz_component(subscript)

class GeometryNodeSocket(NodeSocket):
    type_to_node = {
                float: (bpy.types.ShaderNodeValue, None),
                int: (bpy.types.FunctionNodeInputInt, 'integer'),
                bool: (bpy.types.FunctionNodeInputBool, 'boolean'),
                str: (bpy.types.FunctionNodeInputString, 'string'),
                tuple: {
                    3:(bpy.types.FunctionNodeInputVector,'vector') ,
                    4:(bpy.types.FunctionNodeInputColor,'color')
                    }
                }

    def _compare(self, other, operation):
        from .dynamic.geometry import compare
        return compare(operation=operation, a=self, b=other)

    def __eq__(self, other):
        if self._socket.type == 'BOOLEAN':
            return self._boolean_math(other, 'XNOR')
        else:
            return self._compare(other, 'EQUAL')

    def __ne__(self, other):
        if self._socket.type == 'BOOLEAN':
            return self._boolean_math(other, 'XOR')
        else:
            return self._compare(other, 'NOT_EQUAL')

    def __lt__(self, other):
        return self._compare(other, 'LESS_THAN')

    def __le__(self, other):
        return self._compare(other, 'LESS_EQUAL')

    def __gt__(self, other):
        return self._compare(other, 'GREATER_THAN')

    def __ge__(self, other):
        return self._compare(other, 'GREATER_EQUAL')

    def _boolean_math(self, other, operation, reverse=False):
        boolean_math_node = Node(bpy.types.FunctionNodeBooleanMath)._node
        boolean_math_node.operation = operation
        a = None
        b = None
        for node_input in boolean_math_node.inputs:
            if not node_input.enabled:
                continue
            elif a is None:
                a = node_input
            else:
                b = node_input
        State.current_node_tree.link(self._socket, a)
        if other is not None:
            if issubclass(type(other), self.__class__):
                State.current_node_tree.link(other._socket, b)
            else:
                b.default_value = other
        return self.__class__(boolean_math_node.outputs[0])

    def __and__(self, other):
        return self._boolean_math(other, 'AND')

    def __rand__(self, other):
        return self._boolean_math(other, 'AND', reverse=True)

    def __or__(self, other):
        return self._boolean_math(other, 'OR')

    def __ror__(self, other):
        return self._boolean_math(other, 'OR', reverse=True)

    def __invert__(self):
        if self._socket.type == 'BOOLEAN':
            return self._boolean_math(None, 'NOT')
        else:
            return super().__invert__(self)

    @staticmethod
    def enum_socket_type_to_attribute_type(enum_socket_type):
        match enum_socket_type:
            case 'VALUE':
                return 'FLOAT'
            case 'VECTOR':
                return 'FLOAT_VECTOR'
            case 'RGBA':
                return 'FLOAT_COLOR'
            case 'ROTATION':
                return 'QUATERNION'
            case _:
                return enum_socket_type

    def capture(self, value, **kwargs):
        data_type = GeometryNodeSocket.enum_socket_type_to_attribute_type(value._socket.type)
        res = self.capture_attribute(data_type=data_type, value=value, **kwargs)
        return res.geometry, res.attribute

    def __getitem__(self, subscript):
        result = super().__getitem__(subscript)
        if result is not None:
            return result

        from .dynamic.geometry import index, position

        if isinstance(subscript, tuple):
            accessor = subscript[0]
            args = subscript[1:]
        else:
            accessor = subscript
            args = []
        sample_mode = SampleMode.INDEX if len(args) < 1 else args[0]
        domain = 'POINT' if len(args) < 2 else (args[1].value if isinstance(args[1], enum.Enum) else args[1])
        sample_position = None
        sampling_index = None
        if isinstance(accessor, slice):
            data_type = GeometryNodeSocket.enum_socket_type_to_attribute_type(accessor.start._socket.type)
            value = accessor.start
            match sample_mode:
                case SampleMode.INDEX:
                    sampling_index = accessor.stop
                case SampleMode.NEAREST_SURFACE:
                    sample_position = accessor.stop
                case SampleMode.NEAREST:
                    sample_position = accessor.stop
            if accessor.step is not None:
                domain = accessor.step.value if isinstance(accessor.step, enum.Enum) else accessor.step
        else:
            data_type = GeometryNodeSocket.enum_socket_type_to_attribute_type(accessor._socket.type)
            value = accessor
        match sample_mode:
            case SampleMode.INDEX:
                return self.sample_index(
                    data_type=data_type,
                    domain=domain,
                    value=value,
                    index=sampling_index or index()
                )
            case SampleMode.NEAREST_SURFACE:
                return self.sample_nearest_surface(
                    data_type=data_type,
                    value=value,
                    sample_position=sample_position or position()
                )
            case SampleMode.NEAREST:
                return self.sample_index(
                    data_type=data_type,
                    value=value,
                    index=self.sample_nearest(domain=domain, sample_position=sample_position or position())
                )

class ShaderNodeSocket(NodeSocket):
    type_to_node = {
                float: ( bpy.types.ShaderNodeValue, None),
                tuple: { 4:(bpy.types.ShaderNodeRGB, None) }
                }

class CompositorNodeSocket(NodeSocket):
    type_to_node = {
                float: (bpy.types.CompositorNodeValue, None),
                tuple: {}
                }
    @classmethod
    @property
    def class_math(cls):
        from .dynamic.compositor import math
        return math

class TextureNodeSocket(NodeSocket):
    @classmethod
    @property
    def class_math(cls):
        from .dynamic.texture import math
        return math

def get_shortened_socket_type_name(socket_type):
    return socket_type.__name__.replace('NodeSocket', '')

def create_node_socket_subclasses_for_annotations(base_node_socket_class, module):
    for socket_type in get_bpy_subclasses(bpy.types.NodeSocketStandard):
        name = get_shortened_socket_type_name(socket_type)
        module.__dict__[name] = type(name, (base_node_socket_class,), { 'socket_type': socket_type.__name__, '__module__': module.__name__})


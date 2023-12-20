import bpy
import enum
from functools import partial, partialmethod
from collections import defaultdict
from . import nodesocket
from .nodetree import NodeTree
from .node import Node
from .util import lower_snake_case, title_case, upper_snake_case, get_bpy_subclasses, get_unique_subclass_properties, _as_iterable
from mathutils import Vector

class NodeInfo():
    def __init__(self, node_type):
        self.type = node_type
        self.func_name = lower_snake_case(node_type.bl_rna.name)
        self.namespace = title_case(node_type.bl_rna.name)
        self.outputs = {}
        self.primary_arg = None
        self.default_value = defaultdict(lambda: defaultdict(list))
        self.input_index = {}

class NodeRegistrar:
    enum_socket_type = {}
    socket_type_with_none_subtype = {}
    all_node_info = {}

    def __init__(self):
        self.node_socket_class = None
        self.node_info = None
        self.node_infos=[]
        self.enums = defaultdict(list)

    @staticmethod
    def remove_socket_subtype(socket_type):
        return NodeRegistrar.socket_type_with_none_subtype[NodeRegistrar.enum_socket_type[socket_type]]

    def register_node_types(self,node_types,node_tree_type):
        self.node_tree=NodeTree.node_trees.new('temp_node_tree', f"{node_tree_type}NodeTree")
        self.node_socket_class = getattr(nodesocket, f"{node_tree_type}NodeSocket")
        for node_type in node_types:
            self.register_node_type(node_type)
        self.add_math_functions()
        self.clean_up()

    def register_node_type(self,node_type):
        try:
            self.node_instance = self.node_tree.nodes.new(node_type.__name__)
        except:
            return
        self.node_info = NodeInfo(node_type)
        self.make_node_build_function()
        self.make_node_build_for_nodesocket_fluent_interface()
        self.parse_node_properties()
        self.parse_node_inputs()
        self.parse_node_outputs()
        self.node_infos.append(self.node_info)
        NodeRegistrar.all_node_info[node_type] = self.node_info

    def make_node_build_function(self):
        func = partial(Node.build_node,primary_arg=None,node_type=self.node_info.type)
        globals()[self.node_info.func_name] = func

    def make_node_build_for_nodesocket_fluent_interface(self):
        method = partialmethod(Node.build_node, node_type=self.node_info.type)
        setattr( self.node_socket_class, self.node_info.func_name,  method)

    def parse_node_properties(self):
        for node_prop in get_unique_subclass_properties(self.node_info.type):
            argname = node_prop.identifier
            if node_prop.type == 'ENUM':
                typename = self.create_enum(node_prop)
            else:
                typename = node_prop.type.title()

            default_value = getattr(self.node_instance,node_prop.identifier)
            if type(default_value) == Vector:
                default_value = tuple(default_value)
            self.node_info.input_index[node_prop.identifier] = len(self.node_info.default_value[argname][typename])
            self.node_info.default_value[argname][typename].append(default_value)

    def parse_node_inputs(self):
        for node_input in self.node_instance.inputs:
            argname = lower_snake_case(node_input.name)
            typename = nodesocket.get_shortened_socket_type_name(type(node_input))
            if node_input.is_multi_input:
                typename = f"List[{typename}]"

            default_value = getattr(node_input,'default_value',None)
            if node_input.type in ['VALUE','INT','VECTOR','RGBA','ROTATION']:
                default_value = tuple(_as_iterable(default_value))
            self.node_info.input_index[node_input.identifier] = len(self.node_info.default_value[argname][typename])
            self.node_info.default_value[argname][typename].append(default_value)


            socket_type = 'NodeSocket'+typename
            self.enum_socket_type[socket_type] = node_input.type
            if node_input.bl_subtype_label == 'None':
                self.socket_type_with_none_subtype[node_input.type] = socket_type

            if self.node_info.primary_arg is None:
                self.node_info.primary_arg = {'argname':argname,'typename': typename}

    def parse_node_outputs(self):
        for node_output in self.node_instance.outputs:
            outputname = lower_snake_case(node_output.name)
            typename = nodesocket.get_shortened_socket_type_name(type(node_output))
            self.node_info.outputs[outputname] = typename

    def create_enum(self,prop):
        enum_name = title_case(prop.identifier)
        enum_cases = { upper_snake_case(enum_item.identifier): enum_item.identifier for enum_item in prop.enum_items }
        enum_type = enum.Enum(enum_name, enum_cases)

        if self.node_info.namespace not in globals():
            globals()[self.node_info.namespace] = type(self.node_info.namespace, (), {})
        setattr(globals()[self.node_info.namespace], enum_name, enum_type)
        self.enums[self.node_info.namespace].append(enum_type)

        return  f"{self.node_info.namespace}.{enum_name}"

    math_aliases= {'cosine':'cos','sine':'sin','tangent':'tan',
                'arcsine':'asin','arccosine':'acos','arctangent':'atan','arctan2':'atan2'}
    def add_math_functions(self):
        def _math(*vectors_or_values,operation=None):
            if type(vectors_or_values[0]) == tuple:
                vector_like = True
            elif isinstance(vectors_or_values[0],nodesocket.NodeSocket):
                vector_like = vectors_or_values[0]._socket.type in  ['VECTOR','RGBA']
            else:
                vector_like = False
            if len(vectors_or_values) == 1:
                vectors_or_values = vectors_or_values[0]
            if vector_like:
                return vector_math(operation=operation, vector=vectors_or_values)
            else:
                return math(operation=operation, value=vectors_or_values)

        operations = list(Math.Operation.__members__) + list(VectorMath.Operation.__members__)
        for operation in operations:
            if lower_snake_case(operation) not in globals():
                globals()[lower_snake_case(operation)]= partial(_math,operation=operation)

        for name,alias in self.__class__.math_aliases.items():
            globals()[alias]=globals()[name]

    def clean_up(self):
        NodeTree.node_trees.remove(self.node_tree)

def collect_node_types_to_register():
    node_types_to_register = []
    for node_type in get_bpy_subclasses(bpy.types.Node):
        if node_type.is_registered_node_type():
            node_types_to_register.append(node_type)
    return node_types_to_register

def register_node_types(node_tree_type):
    node_types_to_register = collect_node_types_to_register()
    nr = NodeRegistrar()
    nr.register_node_types(node_types_to_register,node_tree_type)
    return nr
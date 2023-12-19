import bpy
import inspect
from . import arrange
from . import nodesocket
from .state import State
from .static.input_group import InputGroup
from functools import partial
from .node import NodeOutputs


class InputInfo:
    def __init__(self,name,socket_type,default_value,index,group_param=None):
        from .noderegistrar import NodeRegistrar as nr
        self.name = name.replace('_', ' ').title()
        self.socket_type = nr.remove_socket_subtype(socket_type)
        self.default_value = default_value
        self.index = index
        self.group_param = group_param

class ParamInfo:
    def __init__(self,name,is_input_group=False,builder_input=None):
        self.name = name
        self.is_input_group = is_input_group
        self.input_infos = []
        self.builder_input = builder_input

class NodeTree:
    @classmethod
    @property
    def node_trees(cls):
        return bpy.data.node_groups

    def __init__(self,node_tree_name=None,**kwargs):
        self.node_tree_name = node_tree_name if node_tree_name else self.__class__.__name__
        self._node_tree = self.get_node_tree()
        for key,value in kwargs.items():
            setattr(self,key,value)

    def get_node_tree(self):
        node_tree = NodeTree.node_trees.get(self.node_tree_name)
        if node_tree is None:
            node_tree = NodeTree.node_trees.new(self.node_tree_name,f"{self.__class__.node_tree_type}NodeTree")
        return node_tree

    def build_tree(self,builder):
        self.builder = builder
        self.builder_is_generator = inspect.isgeneratorfunction(builder)

        State.NodeSocket = self.get_node_socket_class()
        State.current_node_tree = self

        self.clear_nodes()
        self.param_infos = self.get_param_infos()
        self.set_input_sockets()
        self.builder_outputs = self.run_builder()
        self.set_output_sockets()

        arrange._arrange(self._node_tree)

        return self.group_reference

    def clear_nodes(self):
        self._node_tree.nodes.clear()

    def new_node(self,node_type):
        return self._node_tree.nodes.new(node_type)

    def link(self,from_socket,to_socket):
        self._node_tree.links.new(from_socket,to_socket)

    def get_node_socket_class(self):
        return getattr(nodesocket,f"{self.__class__.node_tree_type}NodeSocket")

    def create_group_input_node(self):
        return self.new_node('NodeGroupInput')

    def create_group_output_node(self):
        return self.new_node('NodeGroupOutput')

    @property
    def inputs(self):
        return [i for i in self._node_tree.interface.items_tree if i.item_type == 'SOCKET' and i.in_out == 'INPUT']

    @property
    def outputs(self):
        return [i for i in self._node_tree.interface.items_tree if i.item_type == 'SOCKET' and i.in_out == 'OUTPUT']

    def limit_socket_count(self,sockets,count):
         for socket in sockets[count:]:
            self._node_tree.interface.remove(socket)

    def get_param_infos(self):
        param_infos = []
        self.input_count = 0
        for param in inspect.signature(self.builder).parameters.values():
            if issubclass(param.annotation, InputGroup):
                param_info = self.get_param_info_for_input_group(param)
            else:
                param_info = self.get_param_info_for_single_input(param)
            param_infos.append( param_info )

        return param_infos

    def get_param_info_for_input_group(self,param):
        param_info=ParamInfo(param.name, is_input_group=True, builder_input=param.annotation())
        for group_param, group_annotation in param.annotation.__annotations__.items():
            name = param.annotation.prefix+group_param
            socket_type = group_annotation.socket_type
            default_value = getattr( param_info.builder_input, group_param, None)
            param_info.input_infos.append( InputInfo(name,socket_type,default_value,self.input_count,group_param) )
            self.input_count += 1

        return param_info

    def get_param_info_for_single_input(self,param):
        NodeTree.validate_param(param)
        param_info=ParamInfo(param.name)
        name = param.name
        socket_type = param.annotation.socket_type
        default_value = None if param.default is inspect.Parameter.empty else param.default
        param_info.input_infos = [ InputInfo(name,socket_type,default_value,self.input_count) ]
        self.input_count += 1

        return param_info

    @staticmethod
    def validate_param(param):
        if param.annotation == inspect.Parameter.empty:
            raise Exception(f"Tree input '{param.name}' has no type specified. Please annotate with a valid node input type.")
        if not issubclass(param.annotation, nodesocket.NodeSocket):
            raise Exception(f"Type of tree input '{param.name}' is not a valid 'NodeSocket' subclass.")

    def set_input_sockets(self):
        group_input_node = self.create_group_input_node()
        self._inputs = self.inputs
        for param_info in self.param_infos:
            for input_info in param_info.input_infos:
                i = input_info.index
                self.set_tree_input(i,input_info)
                if param_info.is_input_group:
                    setattr(param_info.builder_input,input_info.group_param,State.NodeSocket.create(group_input_node.outputs[i]) )
                else:
                    param_info.builder_input = State.NodeSocket.create(group_input_node.outputs[i])

        self.limit_socket_count(self._inputs,self.input_count)

    def set_tree_input(self,i,input_info):
        if i < len(self._inputs):
            self._inputs[i].name = input_info.name
            self._inputs[i].socket_type = input_info.socket_type
            tree_input = self._inputs[i]
        else:
            tree_input = self._node_tree.interface.new_socket( name=input_info.name,socket_type=input_info.socket_type, in_out='INPUT')

        if input_info.default_value is not None:
            tree_input.default_value = input_info.default_value

    def run_builder(self):
        builder_inputs = { param_info.name:param_info.builder_input for param_info in self.param_infos }
        builder_outputs = self.builder(**builder_inputs)

        return NodeOutputs.create(builder_outputs)

    def set_output_sockets(self):
        group_output_node = self.create_group_output_node()

        self._outputs = self.outputs
        for i, (output_name, output_socket) in enumerate(self.builder_outputs.items()):
            self.set_tree_output(i,output_name,output_socket)
            self.link(output_socket._socket, group_output_node.inputs[i])

        self.limit_socket_count(self._outputs,len(self.builder_outputs))

    def set_tree_output(self,i,output_name,output_socket):
        if i < len(self._outputs):
            self._outputs[i].name = output_name.title()
            self._outputs[i].socket_type = output_socket.socket_type
        else:
            self._node_tree.interface.new_socket(socket_type=output_socket.socket_type, name=output_name.title(), in_out='OUTPUT')

    def group_reference(self,*args,**kwargs):
        return self.nodegroup(node_tree=self._node_tree,*args,**kwargs)

class GeometryNodeTree(NodeTree):
    node_tree_type = 'Geometry'
    def __init__(self,node_tree_name=None):
        from .dynamic.geometry import geometrynodegroup
        self.nodegroup = geometrynodegroup
        super().__init__(node_tree_name)

    def get_node_tree(self):
        node_tree = super().get_node_tree()
        node_tree.is_modifier = True
        return node_tree

    def run_builder(self):
        builder_outputs = super().run_builder()
        if self.builder_is_generator and self.all_outputs_geometry(builder_outputs):
            from .dynamic.geometry import join_geometry
            builder_outputs = join_geometry( geometry=list(builder_outputs), get_socket_if_singular_output=False )

        return builder_outputs

    def all_outputs_geometry(self,outputs):
        if hasattr(outputs, '__iter__'):
            return all( map(lambda x: issubclass(type(x), State.NodeSocket) and x._socket.type == 'GEOMETRY', outputs ) )

class ShaderNodeTree(NodeTree):
    node_tree_type = 'Shader'
    @classmethod
    @property
    def materials(cls):
        return bpy.data.materials

    def __init__(self,node_tree_name=None,**kwargs):
        from .dynamic.shader import shadernodegroup
        self.nodegroup = shadernodegroup
        self.material_tree = False
        super().__init__(node_tree_name,**kwargs)
    def get_material(self):
        material = ShaderNodeTree.materials.get(self.node_tree_name)
        if material is None:
            material = ShaderNodeTree.materials.new(self.node_tree_name)
        return material
    def get_material_node_tree(self):
        material = self.get_material()
        material.use_nodes = True
        return material.node_tree

    def set_material(self):
        from .dynamic.shader import material_output
        self._node_tree = self.get_material_node_tree()
        self.clear_nodes()
        group_node = self.nodegroup(node_tree=self.get_node_tree(),return_node=True)._node
        material_output_node = material_output(return_node=True)._node
        self.link(group_node.outputs[0], material_output_node.inputs['Surface'])
        arrange._arrange(self._node_tree)
        self._node_tree = self.get_node_tree()

    def build_tree(self, builder):
        group_reference = super().build_tree(builder)
        if self.material_tree:
            self.set_material()
            return self.get_material()
        else:
            return group_reference

class CompositorNodeTree(NodeTree):
    node_tree_type = 'Compositor'
    def __init__(self,node_tree_name=None):
        from .dynamic.compositor import compositornodegroup
        self.nodegroup = compositornodegroup
        super().__init__(node_tree_name)

class TextureNodeTree(NodeTree):
    node_tree_type = 'Texture'
    def __init__(self,node_tree_name=None):
        from .dynamic.texture import texturenodegroup
        self.nodegroup = texturenodegroup
        super().__init__(node_tree_name)

def nodetree(builder=None,node_tree_name=None,node_tree_class=None,**kwargs):
    if callable(builder):
        node_tree_name = node_tree_name if node_tree_name else builder.__name__
        return node_tree_class(node_tree_name,**kwargs).build_tree(builder)
    else:
        return partial(nodetree,node_tree_name=builder,node_tree_class=node_tree_class,**kwargs)

if bpy.app.version[0] < 4:
    from .nodetree_blender3 import *

geometrytree = partial(nodetree,node_tree_class=GeometryNodeTree)
tree = geometrytree
shadertree = partial(nodetree,node_tree_class=ShaderNodeTree)
materialtree = partial(shadertree,material_tree=True)
compositortree = partial(nodetree,node_tree_class=CompositorNodeTree)
texturetree = partial(nodetree,node_tree_class=TextureNodeTree)



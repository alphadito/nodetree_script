import bpy
from .nodetree import NodeTree as FutureNodeTree
from .nodetree import GeometryNodeTree as FutureGeometryNodeTree
from .nodetree import ShaderNodeTree as FutureShaderNodeTree
from .nodetree import CompositorNodeTree as FutureCompositorNodeTree
from .nodetree import TextureNodeTree as FutureTextureNodeTree


class NodeTree(FutureNodeTree):
    @property
    def inputs(self):
        return self._node_tree.inputs
    @property
    def outputs(self):
        return self._node_tree.outputs

    def limit_socket_count(self,sockets,count):
        if type(sockets.rna_type) == bpy.types.NodeTreeInputs:
            for socket in sockets[count:]:
                self.inputs.remove(socket)
        else:
            for socket in sockets[count:]:
                self.outputs.remove(socket)

    def set_tree_input(self,i,input_info):
        if i < len(self._inputs):
            if self._inputs[i].bl_socket_idname != input_info.socket_type:
                self.limit_socket_count(self._inputs,i)
                self._inputs = self.inputs
                tree_input = self._node_tree.inputs.new(input_info.socket_type, input_info.name)
            self._inputs[i].name = input_info.name
            tree_input = self._inputs[i]
        else:
            tree_input = self._node_tree.inputs.new(input_info.socket_type, input_info.name)
        if input_info.default_value is not None:
            tree_input.default_value = input_info.default_value
    def set_tree_output(self, i, output_name, output_socket):
        if i < len(self._outputs):
            if self._outputs[i].bl_socket_idname != output_socket.socket_type:
                self.limit_socket_count(self._outputs,i)
                self._outputs = self.outputs
                self._node_tree.outputs.new(output_socket.socket_type, output_name)
            self._outputs[i].name = output_name.title()
        else:
            self._node_tree.outputs.new(output_socket.socket_type, output_name.title())

FutureGeometryNodeTree.__bases__ = (NodeTree,)
class GeometryNodeTree(FutureGeometryNodeTree):
    def __init__(self,node_tree_name=None):
        from .dynamic.geometry import group
        self.nodegroup = group
        NodeTree.__init__(self,node_tree_name)
    def get_node_tree(self):
        return NodeTree.get_node_tree(self)

FutureShaderNodeTree.__bases__ = (NodeTree,)
class ShaderNodeTree(FutureShaderNodeTree):
    def __init__(self,node_tree_name=None,**kwargs):
        from .dynamic.shader import group
        self.material_tree = False
        self.nodegroup = group
        NodeTree.__init__(self,node_tree_name,**kwargs)

FutureCompositorNodeTree.__bases__ = (NodeTree,)
class CompositorNodeTree(FutureCompositorNodeTree):
    def __init__(self,node_tree_name=None):
        from .dynamic.compositor import group
        self.nodegroup = group
        NodeTree.__init__(self,node_tree_name)

FutureTextureNodeTree.__bases__ = (NodeTree,)
class TextureNodeTree(FutureTextureNodeTree):
    def __init__(self,node_tree_name=None):
        from .dynamic.texture import group
        self.nodegroup = group
        NodeTree.__init__(self,node_tree_name)

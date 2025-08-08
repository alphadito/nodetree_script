import bpy

if bpy.app.version < (4, 5, 0):
    no_args_input_nodes = [bpy.types.ShaderNodeValue,bpy.types.ShaderNodeRGB,bpy.types.CompositorNodeValue]
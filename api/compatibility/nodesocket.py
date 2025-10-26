import bpy

if bpy.app.version < (4, 5, 0):    
    from ..nodesocket import CompositorNodeSocket as FutureCompositorNodeSocket
    class CompositorNodeSocket(FutureCompositorNodeSocket):
        type_to_node = {
                    float: (bpy.types.CompositorNodeValue, None),
                    tuple: {}
                    }
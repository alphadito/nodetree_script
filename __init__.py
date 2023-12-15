# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import os
import webbrowser
import json

from .preferences import GeometryScriptPreferences
from .absolute_path import absolute_path

from .api.arrange import *
from .api.docs import *
from .api.node import *
from .api.noderegistrar import *
from .api.nodesocket import *
from .api.nodetree import *
from .api.state import *
from .api.util import *

from .api.static.attribute import *
from .api.static.curve import *
from .api.static.expression import *
from .api.static.input_group import *
from .api.static.nodetree_to_script import *
from .api.static.sample_mode import *
from .api.static.zone import *

from .api.noderegistrar import register_node_types, NodeRegistrar
node_tree_types = ['Geometry','Shader','Texture','Compositor']

def create_documentation():
    for node_tree_type in node_tree_types:
         noderegistrar = register_node_types(node_tree_type)
         Docs(noderegistrar,node_tree_type).create_documentation()


bpy.app.timers.register(create_documentation)


bl_info = {
    "name" : "Geometry Script",
    "author" : "Carson Katri",
    "description" : "Python scripting for geometry nodes",
    "blender" : (3, 0, 0),
    "version" : (0, 1, 2),
    "location" : "",
    "warning" : "",
    "category" : "Node"
}
class CopySelectedNodes(bpy.types.Operator):
    """Copy Selected Nodes to Clipboard"""
    bl_idname = "node.copy_selected"
    bl_label = "Copy Selected Nodes"

    def execute(self, context):
        if context.space_data.type == 'NODE_EDITOR' and context.space_data.node_tree:
            node_tree = context.space_data.node_tree
            selected_nodes = [node for node in node_tree.nodes if node.select]
            content = '\n'.join([node_to_script(node) for node in selected_nodes])
            bpy.context.window_manager.clipboard = content
            self.report({'INFO'}, f"{len(selected_nodes)} nodes copied to clipboard.")

        return {'FINISHED'}
def menu_func(self, context):
    self.layout.operator(CopySelectedNodes.bl_idname)

class TEXT_MT_templates_geometryscript(bpy.types.Menu):
    bl_label = "Geometry Script"

    def draw(self, _context):
        self.path_menu(
            [os.path.join(os.path.dirname(os.path.realpath(__file__)), "examples")],
            "text.open",
            props_default={"internal": True},
            filter_ext=lambda ext: (ext.lower() == ".py")
        )

class OpenDocumentation(bpy.types.Operator):
    bl_idname = "geometry_script.open_documentation"
    bl_label = "Open Documentation"

    doc_type: bpy.props.EnumProperty(
        name="Documentation Type",
        items = [(node_tree_type, node_tree_type, "") for node_tree_type in node_tree_types]
    )
    def execute(self, context):
        webbrowser.open('file://' + absolute_path(f'docs/{self.doc_type.lower()}_documentation.html'))
        return {'FINISHED'}

class GeometryScriptSettings(bpy.types.PropertyGroup):
    auto_resolve: bpy.props.BoolProperty(name="Auto Resolve", default=False, description="If the file is edited externally, automatically accept the changes")

class GeometryScriptMenu(bpy.types.Menu):
    bl_idname = "TEXT_MT_geometryscript"
    bl_label = "Geometry Script"

    def draw(self, context):
        layout = self.layout

        text = context.space_data.text
        if text and len(text.filepath) > 0:
            layout.prop(context.scene.geometry_script_settings, 'auto_resolve')

        for node_tree_type in node_tree_types:
            layout.operator(OpenDocumentation.bl_idname, text=f"Open {node_tree_type} Documentation").doc_type = node_tree_type

def templates_menu_draw(self, context):
    self.layout.menu(TEXT_MT_templates_geometryscript.__name__)

def editor_header_draw(self, context):
    self.layout.menu(GeometryScriptMenu.bl_idname)

def auto_resolve():
    if bpy.context.scene.geometry_script_settings.auto_resolve:
        try:
            for area in bpy.context.screen.areas:
                for space in area.spaces:
                    if space.type == 'TEXT_EDITOR':
                        with bpy.context.temp_override(area=area, space=space):
                            text = bpy.context.space_data.text
                            if text and text.is_modified:
                                bpy.ops.text.resolve_conflict(resolution='RELOAD')
                                if bpy.context.space_data.use_live_edit:
                                    bpy.ops.text.run_script()
        except:
            pass
    return 1

def register():
    bpy.utils.register_class(TEXT_MT_templates_geometryscript)
    bpy.types.TEXT_MT_templates.append(templates_menu_draw)
    bpy.utils.register_class(GeometryScriptSettings)
    bpy.utils.register_class(GeometryScriptPreferences)
    bpy.utils.register_class(OpenDocumentation)
    bpy.utils.register_class(GeometryScriptMenu)

    bpy.types.TEXT_HT_header.append(editor_header_draw)

    bpy.types.Scene.geometry_script_settings = bpy.props.PointerProperty(type=GeometryScriptSettings)

    bpy.app.timers.register(auto_resolve, persistent=True)

    bpy.utils.register_class(CopySelectedNodes)
    bpy.types.NODE_MT_context_menu.append(menu_func)

def unregister():
    bpy.utils.unregister_class(TEXT_MT_templates_geometryscript)
    bpy.types.TEXT_MT_templates.remove(templates_menu_draw)
    bpy.utils.unregister_class(GeometryScriptSettings)
    bpy.utils.unregister_class(GeometryScriptPreferences)
    bpy.utils.unregister_class(OpenDocumentation)
    bpy.utils.unregister_class(GeometryScriptMenu)
    bpy.types.TEXT_HT_header.remove(editor_header_draw)

    bpy.utils.unregister_class(CopySelectedNodes)
    bpy.types.NODE_MT_context_menu.remove(menu_func)
    try:
        bpy.app.timers.unregister(auto_resolve)
    except:
        pass

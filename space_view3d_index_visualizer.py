# <pep8-80 compliant>

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bgl
import blf
import bmesh
import mathutils
from bpy_extras import view3d_utils
from bpy.props import *
from collections import namedtuple

__author__ = "Nutti <nutti.metro@gmail.com>"
__status__ = "Production"
__version__ = "1.0"
__date__ = "18 Jul 2015"

bl_info = {
    "name": "Index Visualizer",
    "author": "Nutti",
    "version": (1, 0),
    "blender": (2, 74, 0),
    "location": "View3D > Index Visualizer",
    "description": "Visualize indices of vertex/edge/face in View3D mode.",
    "warning": "",
    "support": "COMMUNITY",
    "wiki_url": "",
    "tracker_url": "",
    "category": "3D View"
}

Rect = namedtuple('Rect', 'x0 y0 x1 y1')

addon_keymaps = []


def get_canvas(context, pos, ch_count, font_size):
    """Get canvas to be renderred index."""
    sc = context.scene
    
    width = ch_count * font_size * 1.0
    height = font_size * 1.5

    center_x, center_y, len_x, len_y = pos.x, pos.y, width, height
    
    x0 = int(center_x - len_x * 0.5)
    y0 = int(center_y - len_y * 0.5)
    x1 = int(center_x + len_x * 0.5)
    y1 = int(center_y + len_y * 0.5)
    return Rect(x0, y0, x1, y1)


class IVRenderer(bpy.types.Operator):
    """Rendering index"""
    
    bl_idname = "view3d.iv_renderer"
    bl_label = "Index renderer"

    __handle = None
    __timer = None
    
    @staticmethod
    def handle_add(self, context):
        IVRenderer.__handle = bpy.types.SpaceView3D.draw_handler_add(
            IVRenderer.render_indices,
            (self, context), 'WINDOW', 'POST_PIXEL')
    
    @staticmethod
    def handle_remove(self, context):
        if IVRenderer.__handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(
                IVRenderer.__handle, 'WINDOW')
            IVRenderer.__handle = None
    
    @classmethod
    def is_running(self):
        return IVRenderer.__handle is not None

    @staticmethod
    def __render_data(context, data):
        for d in data:
            IVRenderer.__render_each_data(context, d)
    
    @staticmethod
    def __render_each_data(context, data):
        sc = context.scene
        # setup rendering region
        area = context.area        
        if area.type != "VIEW_3D":
            return
        for region in area.regions:
            if region.type == "WINDOW":
                break
        else:
            return
        for space in area.spaces:
            if space.type == "VIEW_3D":
                break
        else:
            return
        loc_on_screen = view3d_utils.location_3d_to_region_2d(
            region,
            space.region_3d,
            data[1])

        rect = get_canvas(context, loc_on_screen, len(str(data[0])), sc.iv_font_size)
        positions = [
            [rect.x0, rect.y0],
            [rect.x0, rect.y1],
            [rect.x1, rect.y1],
            [rect.x1, rect.y0]
            ]

        # render box
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBegin(bgl.GL_QUADS)
        box_color_r, box_color_g, box_color_b, box_color_a = sc.iv_box_color
        bgl.glColor4f(box_color_r, box_color_g, box_color_b, box_color_a)
        for (v1, v2) in positions:
            bgl.glVertex2f(v1, v2)
        bgl.glEnd()

        # render index
        font_size = sc.iv_font_size
        blf.size(0, font_size, 72)
        blf.enable(0, blf.SHADOW)
        blf.shadow_offset(0, 1, -1)
        blf.shadow(0, 5, 0.0, 0.0, 0.0, 0.0)
        blf.position(0, rect.x0 + (rect.x1 - rect.x0) * 0.18, rect.y0 + (rect.y1 - rect.y0) * 0.24, 0)
        text_color_r, text_color_g, text_color_b, text_color_a = sc.iv_text_color
        bgl.glColor4f(text_color_r, text_color_g, text_color_b, text_color_a)
        blf.draw(0, str(data[0]))
        blf.blur(0, 0)
        blf.disable(0, blf.SHADOW)

    @staticmethod
    def __get_rendered_face(context, bm, world_mat):
        rendered_object = []
        for face in bm.faces:
            if face.select:
                ave = mathutils.Vector((0.0, 0.0, 0.0))
                for v in face.verts:
                    ave = ave + v.co
                ave = ave / len(face.verts)
                rendered_object.append((face.index, world_mat * ave))
        return rendered_object

    @staticmethod
    def __get_rendered_edge(context, bm, world_mat):
        rendered_object = []
        for edge in bm.edges:
            if edge.select:
                ave = mathutils.Vector((0.0, 0.0, 0.0))
                for v in edge.verts:
                    ave = ave + v.co
                ave = ave / len(edge.verts)
                rendered_object.append((edge.index, world_mat * ave))
        return rendered_object

    @staticmethod
    def __get_rendered_vert(context, bm, world_mat):
        rendered_object = []
        for vert in bm.verts:
            if vert.select:
                rendered_object.append((vert.index, world_mat * vert.co))
        return rendered_object

    @staticmethod
    def render_indices(self, context):
        wm = context.window_manager
        sc = context.scene

        if not IVRenderer.is_valid_context(context):
            return

        # get rendered object
        obj = bpy.context.active_object
        world_mat = obj.matrix_world
        bm = bmesh.from_edit_mesh(obj.data)
        sel_mode = bm.select_mode
        rendered_data = None
        if "VERT" in sel_mode:
            rendered_data = IVRenderer.__get_rendered_vert(context, bm, world_mat)
        if "EDGE" in sel_mode:
            rendered_data = IVRenderer.__get_rendered_edge(context, bm, world_mat)
        if "FACE" in sel_mode:
            rendered_data = IVRenderer.__get_rendered_face(context, bm, world_mat)

        IVRenderer.__render_data(context, rendered_data)

    @staticmethod
    def is_valid_context(context):

        obj = context.object

        if obj is None \
                or obj.type != 'MESH' \
                or context.object.mode != 'EDIT':
            return False
        
        for space in context.area.spaces:
            if space.type == 'VIEW_3D':
                break
        else:
            return False

        return True


class IVOperator(bpy.types.Operator):
    bl_idname = "view3d.iv_op"
    bl_label = "Index Visualizer"
    bl_description = "Index Visualizer"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        if context.area.type == "VIEW_3D":
            if IVRenderer.is_running() is False:
                IVRenderer.handle_add(self, context)
            else:
                IVRenderer.handle_remove(self, context)
            for area in context.screen.areas:
                if area.type == context.area.type:
                    area.tag_redraw()
            return {"FINISHED"}
        else:
            return {"CANCELLED"}

    @classmethod
    def release_handle(self, context):
        IVRenderer.handle_remove(self, context)

    @classmethod
    def is_running(self):
        return IVRenderer.is_running()

    @staticmethod
    def is_valid_context(context):
        return IVRenderer.is_valid_context(context)


# UI View
class OBJECT_PT_IV(bpy.types.Panel):
    bl_label = "Index Visualizer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        sc = context.scene
        layout = self.layout
        if not IVOperator.is_running():
            layout.operator(IVOperator.bl_idname, text="Start", icon="PLAY")
        else:
            layout.operator(IVOperator.bl_idname, text="Stop", icon="PAUSE")
            layout.prop(sc, "iv_box_color")
            layout.prop(sc, "iv_text_color")
            layout.label(text="Size:")
            layout.prop(sc, "iv_font_size", text="Text")

    @classmethod
    def poll(cls, context):
        return bpy.types.VIEW3D_OT_iv_op.is_valid_context(context)


def init_properties():
    sc = bpy.types.Scene
    sc.iv_box_color = FloatVectorProperty(
        name="Box Color",
        description="Box color",
        default=(0.0, 0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
        subtype="COLOR",
        size=4)
    sc.iv_text_color = FloatVectorProperty(
        name="Text Color",
        description="Text color",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        subtype="COLOR",
        size=4)
    sc.iv_font_size = IntProperty(
        name="Text Size",
        description="Text size",
        default=13,
        min=10,
        max=100)


def clear_properties():
    sc = bpy.types.Scene
    del sc.iv_font_size
    del sc.iv_text_color
    del sc.iv_box_color


def register():
    bpy.utils.register_module(__name__)
    init_properties()
    # assign shortcut keys
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    key_assign_list = [
        (IVOperator.bl_idname, "I", "PRESS", True, True, False),
        ]
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        for (idname, key, event, ctrl, alt, shift) in key_assign_list:
            kmi = km.keymap_items.new(
                idname, key, event, ctrl=ctrl, alt=alt, shift=shift)
            addon_keymaps.append((km, kmi))


def unregister():
    bpy.types.VIEW3D_OT_iv_op.release_handle(bpy.context)

    bpy.utils.unregister_module(__name__)
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    clear_properties()


if __name__ == "__main__":
    register()


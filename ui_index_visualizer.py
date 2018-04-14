# <pep8-80 compliant>

from math import pi

import bpy
import bgl
import blf
import bmesh
import mathutils

from mathutils import Vector, Matrix
from bpy_extras import view3d_utils
from bpy.props import *
from collections import namedtuple

__author__ = "Nutti <nutti.metro@gmail.com>, tetii"
__status__ = "Production"
__version__ = "2.0"
__date__ = "14 Apr 2018"

bl_info = {
    "name": "Index Visualizer",
    "author": "Nutti, tetii",
    "version": (2, 0),
    "blender": (2, 74, 0),
    "location": "UI > Index Visualizer",
    "description": "Visualize indices of vertex/edge/face in "
                   "View3D and UV Image Editor.",
    "warning": "",
    "support": "COMMUNITY",
    "wiki_url": "",
    "tracker_url": "https://github.com/nutti/Index-Visualizer",
    "category": "UI"
}

Rect = namedtuple('Rect', 'x0 y0 x1 y1')


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


class RenderUVIndexProperties(bpy.types.PropertyGroup):
    loops = BoolProperty(
        name = "Loops",
        default = False
    )
    faces = BoolProperty(
        name = "Faces",
        default = False
    )
    verts = BoolProperty(
        name = "Verts",
        default = False
    )
    edges = BoolProperty(
        name = "Edges",
        default = False
    )
    font_size = IntProperty(
        name="Text Size",
        description="Text size",
        default=11,
        min=8,
        max=32
    )


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

        rect = get_canvas(context, loc_on_screen, len(str(data[0])),
                          sc.iv_font_size)
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
        blf.position(0, rect.x0 + (rect.x1 - rect.x0) * 0.18,
                     rect.y0 + (rect.y1 - rect.y0) * 0.24, 0)
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
            rendered_data = IVRenderer.__get_rendered_vert(context,
                                                           bm, world_mat)
        if "EDGE" in sel_mode:
            rendered_data = IVRenderer.__get_rendered_edge(context,
                                                           bm, world_mat)
        if "FACE" in sel_mode:
            rendered_data = IVRenderer.__get_rendered_face(context,
                                                           bm, world_mat)

        IVRenderer.__render_data(context, rendered_data)

    @staticmethod
    def is_valid_context(context):
        obj = context.object
        if (obj is None) or (obj.type != 'MESH') or \
           (context.object.mode != 'EDIT'):
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


class RenderUVIndex(bpy.types.Operator):

    bl_idname = "uv.render_uv_index"
    bl_label = "Render UV Index"
    bl_description = "Render UV Index"

    __handle = None

    @classmethod
    def __handle_add(cls, context):
        if cls.__handle is None:
            sie = bpy.types.SpaceImageEditor
            cls.__handle = sie.draw_handler_add(
                cls.__render, (context,), 'WINDOW','POST_PIXEL')

    @classmethod
    def __handle_remove(cls):
        if cls.__handle is not None:
            sie = bpy.types.SpaceImageEditor
            sie.draw_handler_remove(cls.__handle, 'WINDOW')
            cls.__handle = None

    @classmethod
    def release_handle(cls):
        cls.__handle_remove()

    @classmethod
    def is_running(cls):
        return cls.__handle is not None

    @staticmethod
    def is_valid_context(context):
        obj = context.object
        if (obj is None) or (obj.type != 'MESH') or \
           (context.object.mode != 'EDIT'):
            return False

        for space in context.area.spaces:
            if space.type == 'IMAGE_EDITOR':
                break
        else:
            return False

        if (space.image is not None) and (space.image.type == 'RENDER_RESULT'):
            return False

        return True

    @staticmethod
    def __render_text(size, v, s):
        blf.size(0, size, 72)
        blf.position(0, v.x, v.y, 0)
        blf.draw(0, s)

    @classmethod
    def __render(cls, context):
        if not cls.is_valid_context(context):
            return

        for region in context.area.regions:
            if region.type == 'WINDOW':
                break
        else:
            return

        scene = context.scene
        ruvi_props = scene.ruvi_properties
        uv_select_sync = scene.tool_settings.use_uv_select_sync
        black = (0.0, 0.0, 0.0, 1.0)
        quasi_black = (0.0, 0.0, 0.0, 0.3)
        blf.shadow(0, 3, 1.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(0, 2, -2)

        [me, bm, uv_layer] = cls.__init_bmesh(context)

        for f in bm.faces:
            if not f.select and not uv_select_sync:
                continue

            selected_loops_count = 0
            uvc = Vector([0.0, 0.0])    # center uv of the face

            for loop1 in f.loops:
                uv1 = loop1[uv_layer].uv
                uvc += uv1
                if not loop1[uv_layer].select and not uv_select_sync:
                    continue
                selected_loops_count += 1

                # Draw Vert index
                if ruvi_props.verts:
                    if uv_select_sync and not loop1.vert.select:
                        continue
                    cls.__render_text_index(context, region, loop1.vert.index,
                                            uv1, bg_color=quasi_black)

                # Get next loop parameter
                loop2, *arg = cls.__get_2nd_loop(loop1, uv_layer)
                if loop2 is None:
                    continue
                uv2, uvm, uvt, uvn = arg

                # Draw Edge index
                blf.enable(0, blf.ROTATION)
                if ruvi_props.edges:
                    if (not uv_select_sync and loop2[uv_layer].select) or \
                       (uv_select_sync and loop2.vert.select
                            and loop1.edge.select):
                        cls.__render_text_index(context,region,
                                                loop1.edge.index,
                                                uvm, uvt=uvt, uvn=uvn,
                                                bg_color=quasi_black)

                # Draw Loop index
                blf.enable(0, blf.SHADOW)
                if ruvi_props.loops and not uv_select_sync:
                    cls.__render_text_index(context, region, loop1.index,
                                            uvm, uvt=uvt, uvn=uvn,
                                            loop_offset=(1.0, 1.5))

                blf.disable(0, blf.ROTATION)
                blf.disable(0, blf.SHADOW)

            # Draw Face index
            if ruvi_props.faces and \
                ((not uv_select_sync and selected_loops_count) or \
                 (uv_select_sync and f.select)):
                cls.__render_text_index(
                                context,
                                region,
                                f.index,
                                uvc/len(f.loops),
                                )

    def invoke(self, context, event):
        scene = context.scene
        if context.area.type == 'IMAGE_EDITOR':
            if not self.is_running():
                self.__handle_add(context)
            else:
                self.__handle_remove()

            # Redraw all UV/Image Editor Views
            for a in context.screen.areas:
                if a.type == context.area.type: # the filtering is necessary
                    a.tag_redraw()

            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    @staticmethod
    def __get_2nd_loop(loop1, uv_layer):
        loop2 = loop1.link_loop_next
        if (loop2 is None) or (loop1 == loop2):
            return None

        uv1 = loop1[uv_layer].uv
        uv2 = loop2[uv_layer].uv

        # middle vector between uv1 and uv2
        uvm = (uv1 + uv2) / 2.0
        # unit tangent vector from  uv1 to uv2
        uvt = uv2 - uv1
        if uvt.length != 0.0:
            uvt = uvt / uvt.length
        else:
            uvt.x, uvt.y = 1.0, 0.0
        # unit normal vector of uvt
        uvn = Vector([-uvt.y, uvt.x])

        return (loop2, uv2, uvm, uvt, uvn)

    # uv: uv vector to text position
    # uvt: tangent unit vector on uv
    # uvn: normal unit vector on uv
    # loop_offset: additional offset to loop text pos
    @classmethod
    def __render_text_index(cls, context, region, index, uv,
                            uvt=Vector([1.0, 0.0]), uvn=Vector([0.0, 1.0]),
                            loop_offset=(0.0, 0.0), bg_color=None):
        text = str(index)
        ruvi_props = scene = context.scene.ruvi_properties
        additional_offset = loop_offset[ruvi_props.edges]

        # Calcurate position and angle
        v = Vector(region.view2d.view_to_region(uv.x, uv.y))
        text_w, text_h = blf.dimensions(0, text)

        offset = (text_w * uvt + text_h * uvn) / 2
        sub_offset = additional_offset * text_h * uvn

        vxo = Vector([1, 0])
        vxy = Vector([1,-1])
        angle = uvt.angle_signed(vxo)
        if uvt.angle_signed(vxy) > 0:
            v = v - offset + sub_offset
        else:
            v = v + offset + sub_offset
            angle -= pi

        blf.rotation(0, angle)

        # Render index
        if bg_color is not None:
            cls.__draw_background(bg_color, text, v, angle)
        font_size = ruvi_props.font_size
        cls.__render_text(font_size, v, text)

    @staticmethod
    def __draw_background(color, text, vo, angle=0.0):
        text_w, text_h = blf.dimensions(0, text)
        font_w = text_w / len(text)

        a = 0.6
        x1 = vo.x  - font_w / 2
        y1 = vo.y  - text_h / 2 * a
        x2 = x1 + text_w + font_w
        y2 = y1 + text_h * (1 + a)

        poss = [
                Vector([x1, y1]),
                Vector([x1, y2]),
                Vector([x2, y2]),
                Vector([x2, y1])
            ]

        if angle != 0.0:
            rot = Matrix.Rotation(angle, 2, 'Z')
            for i in range(len(poss)):
                poss[i] = rot * (poss[i] - vo) + vo

        # render box
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glColor4f(*color)
        for v in poss:
            bgl.glVertex2f(v.x, v.y)
        bgl.glEnd()
        bgl.glColor4f(1.0, 1.0, 1.0, 1.0)

    @staticmethod
    def __init_bmesh(context):
        me = context.active_object.data
        bm = bmesh.from_edit_mesh(me)
        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()  # currently blender needs both layers.
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        return (me, bm, uv_layer)


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


class IMAGE_PT_RUVI(bpy.types.Panel):

    bl_label = "Visible UV Indecies"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"

    def draw(self, context):
        scene = context.scene
        ruvi_props = scene.ruvi_properties
        layout = self.layout

        if not RenderUVIndex.is_running():
            layout.operator(RenderUVIndex.bl_idname, text="Start", icon="PLAY")
        else:
            layout.operator(RenderUVIndex.bl_idname, text="Stop", icon="PAUSE")

        layout.prop(ruvi_props, "faces")
        layout.prop(ruvi_props, "verts")
        layout.prop(ruvi_props, "edges")

        split = layout.split() # for gray out by use_uv_select_sync
        split.active = not scene.tool_settings.use_uv_select_sync
        split.prop(ruvi_props, "loops")

        layout.prop(ruvi_props, "font_size")

    @classmethod
    def poll(cls, context):
        return bpy.types.UV_OT_render_uv_index.is_valid_context(context)


# Using addon_keymaps[], exeption error is thrown as follow
# RuntimeError: Error: KeyMapItem 'FILE_OT_select' cannot be removed from
# 'View3D Dolly Modal'
def remove_keymap_item(keyconfigs_key, keymap_name, keymap_item_name):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs[keyconfigs_key]

    km = kc.keymaps.get(keymap_name)
    if km is None:
        return False

    for kmi in km.keymap_items:
        if kmi.idname == keymap_item_name:
            km.keymap_items.remove(kmi)
            return True
    else:
        return False


def init_properties():
    sc = bpy.types.Scene
    sc.iv_box_color = FloatVectorProperty(
        name="Box Color",
        description="Box color",
        default=(0.0, 0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
        subtype="COLOR",
        size=4
    )
    sc.iv_text_color = FloatVectorProperty(
        name="Text Color",
        description="Text color",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        subtype="COLOR",
        size=4
    )
    sc.iv_font_size = IntProperty(
        name="Text Size",
        description="Text size",
        default=13,
        min=10,
        max=100
    )
    sc.ruvi_properties = bpy.props.PointerProperty(
        type=RenderUVIndexProperties
    )


def clear_properties():
    sc = bpy.types.Scene
    del sc.iv_font_size
    del sc.iv_text_color
    del sc.iv_box_color
    del sc.ruvi_properties


def register():
    bpy.utils.register_module(__name__)
    init_properties()

    # assign shortcut keys
    wm = bpy.context.window_manager
    kc = wm.keyconfigs["Blender Addon"]
    if kc:
        # 3D View
        km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
        kmi = km.keymap_items.new(IVOperator.bl_idname, 'I', 'PRESS',
                                  ctrl=True, alt=True, shift=False)
        # UV Image Editor
        km = kc.keymaps.new(name="UV Editor", space_type='EMPTY')
        kmi = km.keymap_items.new(RenderUVIndex.bl_idname, 'I', 'PRESS',
                                  ctrl=True, alt=True)


def unregister():
    bpy.types.VIEW3D_OT_iv_op.release_handle(bpy.context)

    remove_keymap_item("Blender Addon", "3D View", IVOperator.bl_idname)
    remove_keymap_item("Blender Addon", "UV Editor", RenderUVIndex.bl_idname)

    bpy.utils.unregister_module(__name__)
    clear_properties()


if __name__ == "__main__":
    try:
        unregister()
    except:
        pass

    register()

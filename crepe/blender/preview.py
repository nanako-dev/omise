# -*- coding: utf-8 -*-
"""assets.glb を読み込んで並べ、EEVEE で確認用の画像を描く。
   /Applications/Blender.app/Contents/MacOS/Blender -b -P preview.py"""
import bpy, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, '..', 'assets.glb'))
objs = {o.name: o for o in bpy.data.objects}
layout = { 'maker': (0, 0, 0), 'tray': (1.5, 0, 0), 'ladle': (1.5, .5, .07), 'tombo': (1.5, 0, .07), 'turner': (1.5, -.45, .07), 'bag': (1.35, -.8, .07), 'bottle': (1.65, -.8, .07),
  'bowl': (-1.0, -1.5, 0), 'fruit_ichigo': (-1.0, -1.5, .05), 'fruit_banana': (-.6, -1.5, 0), 'fruit_kiwi': (-.2, -1.5, 0), 'fruit_mikan': (.2, -1.5, 0), 'fruit_blueberry': (.6, -1.5, 0), 'fruit_chip': (1.0, -1.5, 0), 'cream': (1.4, -1.5, 0),
  'cat': (0, 1.7, 0), 'sign': (-1.4, 1.8, .4), 'plant': (-2.0, 1.2, 0), 'jar': (2.2, 1.2, 0) }
for name, loc in layout.items():
    if name in objs: objs[name].location = loc
# floor
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, -.34)); fl = bpy.context.active_object
m = bpy.data.materials.new('floor'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.83, .62, .42, 1); fl.data.materials.append(m)
# lights + camera
bpy.ops.object.light_add(type='SUN', location=(2, -3, 6)); sun = bpy.context.active_object; sun.data.energy = 3; sun.data.angle = math.radians(12); sun.rotation_euler = (math.radians(35), math.radians(10), math.radians(30))
bpy.ops.object.light_add(type='AREA', location=(-3, -4, 4)); ar = bpy.context.active_object; ar.data.energy = 600; ar.data.size = 5; ar.rotation_euler = (math.radians(50), 0, math.radians(-35))
w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (.98, .9, .93, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = .9
bpy.ops.object.camera_add(location=(.1, -2.6, 1.3)); cam = bpy.context.active_object; cam.rotation_euler = (math.radians(62), 0, 0); cam.data.lens = 60
sc = bpy.context.scene; sc.camera = cam; sc.render.engine = 'BLENDER_EEVEE' if hasattr(bpy.types, 'SceneEEVEE') else 'BLENDER_EEVEE_NEXT'
try: sc.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception: pass
sc.render.resolution_x = 1000; sc.render.resolution_y = 1000; sc.render.filepath = os.path.join(HERE, 'preview.png'); sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print('RENDERED', sc.render.filepath, sc.render.engine)

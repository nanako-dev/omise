# -*- coding: utf-8 -*-
"""クレープシミュレーター用の 3D アセットを Blender で組み立てて GLB に書き出す。
   使い方: /Applications/Blender.app/Contents/MacOS/Blender -b -P build_assets.py
   単位: ゲーム座標 (焼き面の半径 = 1.0)。Blender は Z 上、書き出し時に Y 上へ変換される。
   ゲーム側の z (手前+) は Blender の -y。"""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Euler

random.seed(7)
OUT = bpy.path.abspath('//../assets.glb') if bpy.data.filepath else __file__.rsplit('/', 2)[0] + '/assets.glb'

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- helpers ----------
def lin(hexcol):
    h = hexcol.lstrip('#'); r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    def f(c): return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), 1.0)

MATS = {}
def mat(name, color, rough=.55, coat=0.0, coat_rough=.25, sheen=0.0, metal=0.0, image=None):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = lin(color)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = coat_rough
    p.inputs['Sheen Weight'].default_value = sheen
    p.inputs['Metallic'].default_value = metal
    if image is not None:
        tex = m.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = image
        m.node_tree.links.new(tex.outputs['Color'], p.inputs['Base Color'])
    MATS[name] = m; return m

def smooth(ob):
    for poly in ob.data.polygons: poly.use_smooth = True

def bevel(ob, width=.02, segments=4):
    md = ob.modifiers.new('bevel', 'BEVEL'); md.width = width; md.segments = segments; md.limit_method = 'ANGLE'; md.angle_limit = math.radians(40)

def subsurf(ob, levels=2):
    md = ob.modifiers.new('subsurf', 'SUBSURF'); md.levels = levels; md.render_levels = levels

def add(prim, m, name=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), **kw):
    getattr(bpy.ops.mesh, 'primitive_' + prim + '_add')(location=loc, rotation=rot, **kw)
    ob = bpy.context.active_object; ob.scale = scale; ob.data.materials.append(m); smooth(ob)
    if name: ob.name = name
    return ob

def sphere(m, r, loc, scale=(1, 1, 1), name=None, seg=32):
    return add('uv_sphere', m, name, loc, scale=(r * scale[0], r * scale[1], r * scale[2]), segments=seg, ring_count=seg // 2)

def cyl(m, r1, r2, depth, loc, rot=(0, 0, 0), name=None, verts=48, fill='NGON'):
    return add('cone', m, name, loc, rot, radius1=r1, radius2=r2, depth=depth, vertices=verts, end_fill_type=fill)

def cube(m, size, loc, rot=(0, 0, 0), name=None):
    return add('cube', m, name, loc, rot, scale=(size[0] / 2, size[1] / 2, size[2] / 2), size=2)

def torus(m, R, r, loc, rot=(0, 0, 0), name=None):
    return add('torus', m, name, loc, rot, major_radius=R, minor_radius=r, major_segments=64, minor_segments=16)

def join(obs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join(); ob = bpy.context.active_object; ob.name = name
    return ob

def apply_all(ob):
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    for md in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=md.name)

def image(name, fn, size=256):
    img = bpy.data.images.new(name, size, size, alpha=True)
    y, x = np.mgrid[0:size, 0:size]; u = (x + .5) / size * 2 - 1; v = (y + .5) / size * 2 - 1
    rgba = fn(u, v)  # arrays in sRGB 0..1
    px = np.zeros((size, size, 4), dtype=np.float32)
    for i in range(3):
        c = rgba[i]; px[..., i] = np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
    px[..., 3] = rgba[3]
    img.pixels = px.ravel(); img.pack(); return img

def disc_uv(ob):
    """top face planar UV: (x,y) -> (u,v)"""
    bm = bmesh.new(); bm.from_mesh(ob.data); uv = bm.loops.layers.uv.verify()
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; R = max(max(map(abs, xs)), max(map(abs, ys)))
    for f in bm.faces:
        for l in f.loops: l[uv].uv = (l.vert.co.x / R * .5 + .5, l.vert.co.y / R * .5 + .5)
    bm.to_mesh(ob.data); bm.free()

def spin_profile(points, name, m, steps=48):
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0, z)) for r, z in points]
    for a, b in zip(verts, verts[1:]): bm.edges.new((a, b))
    geom = bm.verts[:] + bm.edges[:]
    bmesh.ops.spin(bm, geom=geom, cent=(0, 0, 0), axis=(0, 0, 1), angle=math.pi * 2, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); ob.data.materials.append(m); smooth(ob)
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
    return ob

# ---------- materials ----------
CREAM = mat('cream', '#fff4e8', .55, coat=.35, coat_rough=.3)
WHITE = mat('white', '#fdfbf8', .45, coat=.5)
PINK = mat('pink', '#f6b9c7', .6, coat=.2)
PINK_SOFT = mat('pinkSoft', '#f9d4dd', .7)
MINT = mat('mint', '#cfe8d8', .7)
WOOD = mat('wood', '#e4b98c', .75)
WOOD_DARK = mat('woodDark', '#cf9a63', .7)
PLATE = mat('plate', '#4b4746', .7)
RIM = mat('rim', '#6a6361', .6)
KNOB = mat('knob', '#ef8fa5', .4, coat=.6)
STEEL = mat('steel', '#d8dbe0', .3, metal=.85)
BATTER = mat('batter', '#f3dca0', .3, coat=.4)
FUR = mat('fur', '#fff1dc', .95, sheen=.5)
FUR_SPOT = mat('furSpot', '#d9a66e', .95)
DARK = mat('dark', '#3b2e26', .2, coat=1.0, coat_rough=.1)
BLUSH = mat('blush', '#f7b3c2', 1.0)
NOSE = mat('nose', '#e68a9a', .6)
LEAF = mat('leaf', '#8fc27a', .8)
LEAF_DARK = mat('leafDark', '#6ea85e', .8)
POT = mat('pot', '#fbeedd', .7)
STRAW = mat('strawberry', '#ea3a4e', .28, coat=1.0, coat_rough=.08)
SEED = mat('seed', '#f7e07a', .5)
BLUE = mat('blueberry', '#4a4b9a', .3, coat=1.0, coat_rough=.15)
BLUE_BLOOM = mat('blueberryBloom', '#8d8fd0', .9)
CHOC = mat('choc', '#3a2214', .35, coat=.8)
ORANGE = mat('orange', '#ffffff', .25, coat=1.0, coat_rough=.1, image=None)
ORANGE_SKIN = mat('orangeSkin', '#fbd49a', .8)
BANANA_SIDE = mat('bananaSide', '#f3e0a0', .5, coat=.4)
KIWI_SIDE = mat('kiwiSide', '#7a5a3a', .8)

# procedural face textures
def kiwi_fn(u, v):
    r = np.sqrt(u * u + v * v); a = np.arctan2(v, u)
    g = np.clip(1 - r, 0, 1)
    R = .78 - .45 * r; G = .86 - .3 * r; B = .35 + .1 * (1 - r)
    core = np.clip((.22 - r) / .08, 0, 1); R = R * (1 - core) + .96 * core; G = G * (1 - core) + .97 * core; B = B * (1 - core) + .86 * core
    streak = (np.sin(a * 24) * .5 + .5) ** 6 * .18 * (r > .22) * (r < .9); R += streak; G += streak * .9; B += streak * .5
    seeds = np.zeros_like(r)
    for i in range(14):
        sa = i / 14 * 2 * np.pi + .3; sr = .36 + .06 * (i % 2); sx, sy = np.cos(sa) * sr, np.sin(sa) * sr
        dx, dy = u - sx, v - sy; ex = dx * np.cos(sa) + dy * np.sin(sa); ey = -dx * np.sin(sa) + dy * np.cos(sa)
        seeds = np.maximum(seeds, np.clip(1 - ((ex / .045) ** 2 + (ey / .024) ** 2), 0, 1) * 4)
    seeds = np.clip(seeds, 0, 1); R = R * (1 - seeds) + .08 * seeds; G = G * (1 - seeds) + .07 * seeds; B = B * (1 - seeds) + .05 * seeds
    alpha = (r <= 1).astype(np.float32)
    return [np.clip(R, 0, 1), np.clip(G, 0, 1), np.clip(B, 0, 1), alpha]
def banana_fn(u, v):
    r = np.sqrt(u * u + v * v)
    R = .99 - .08 * r; G = .96 - .15 * r; B = .80 - .3 * r
    ring = np.clip(1 - np.abs(r - .84) / .05, 0, 1) * .35; R -= ring * .25; G -= ring * .3; B -= ring * .4
    for i in range(3):
        sa = i * 2.09 + .5; sx, sy = np.cos(sa) * .14, np.sin(sa) * .14
        d = np.clip(1 - (((u - sx) / .06) ** 2 + ((v - sy) / .04) ** 2), 0, 1) * 3; d = np.clip(d, 0, 1)
        R = R * (1 - d) + .36 * d; G = G * (1 - d) + .22 * d; B = B * (1 - d) + .1 * d
    for k in range(3):
        a = k * np.pi / 3; line = np.clip(1 - np.abs(u * np.cos(a) + v * np.sin(a)) / .012, 0, 1) * .12 * (r < .8); R -= line; G -= line * .6
    alpha = (r <= 1).astype(np.float32)
    return [np.clip(R, 0, 1), np.clip(G, 0, 1), np.clip(B, 0, 1), alpha]
KIWI_IMG = image('kiwi_face', kiwi_fn); BANANA_IMG = image('banana_face', banana_fn)
KIWI_FACE = mat('kiwiFace', '#ffffff', .22, coat=1.0, coat_rough=.08, image=KIWI_IMG)
BANANA_FACE = mat('bananaFace', '#ffffff', .3, coat=.9, coat_rough=.15, image=BANANA_IMG)
def straw_face_fn(u, v):
    d = np.sqrt((u / 1.0) ** 2 + (v / .62) ** 2)
    core = np.clip((.42 - d) / .22, 0, 1); mid = np.clip((.95 - d) / .5, 0, 1)
    R = .78 + .2 * mid; G = .16 + .62 * mid + .2 * core; B = .22 + .55 * mid + .15 * core
    R = R * (1 - core) + .99 * core; G = np.clip(G, 0, 1); B = np.clip(B, 0, 1)
    a = np.arctan2(v, u); streak = (np.sin(a * 18) * .5 + .5) ** 8 * .25 * (d > .3) * (d < .95)
    R = np.clip(R + streak * .1, 0, 1); G = np.clip(G + streak, 0, 1); B = np.clip(B + streak, 0, 1)
    alpha = (d <= 1.05).astype(np.float32)
    return [R, G, B, alpha]
def mikan_fn(u, v):
    a = np.arctan2(v, u); r = np.sqrt(u * u + v * v)
    sac = (np.sin(u * 60 + np.sin(v * 9) * 2) * .5 + .5) ** 3
    R = .98 - .08 * sac; G = .66 - .14 * sac + .1 * (1 - r); B = .2 + .05 * (1 - r)
    return [np.clip(R, 0, 1), np.clip(G, 0, 1), np.clip(B, 0, 1), np.ones_like(r)]
STRAW_FACE = mat('strawFace', '#ffffff', .28, coat=1.0, coat_rough=.1, image=image('straw_face', straw_face_fn))
MIKAN = mat('mikan', '#ffffff', .22, coat=1.0, coat_rough=.08, image=image('mikan_skin', mikan_fn))
WHIP = mat('whip', '#fffdf8', .62, sheen=.8)

# ---------- crepe maker ----------
def build_maker():
    parts = []
    body = cyl(CREAM, 1.17, 1.12, .3, (0, 0, -.17), name='maker_body'); bevel(body, .07, 6); parts.append(body)
    plate = cyl(PLATE, 1.03, 1.03, .05, (0, 0, -.025)); bevel(plate, .012, 3); parts.append(plate)
    parts.append(torus(RIM, 1.05, .03, (0, 0, 0)))
    knob = cyl(KNOB, .08, .08, .08, (.86, -.78, -.02)); bevel(knob, .02, 4); parts.append(knob)
    parts.append(sphere(WHITE, .018, (.86, -.82, .03)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(sphere(CREAM, .08, (sx * .72, sy * .72 + .05, -.33), (1, 1, .6)))
    ob = join(parts, 'maker'); return ob

# ---------- tray + tools ----------
def build_tray():
    t = cube(WOOD, (.54, 2.0, .07), (0, 0, .035)); bevel(t, .03, 6); t.name = 'tray'; return t
def build_ladle():
    cup = cyl(WHITE, .1, .13, .11, (0, 0, .055)); bevel(cup, .012, 3)
    inner = cyl(BATTER, .115, .115, .01, (0, 0, .1))
    hd = cyl(WHITE, .022, .022, .42, (.27, 0, .12), rot=(0, math.radians(65), 0), verts=16); bevel(hd, .01, 3)
    return join([cup, inner, hd], 'ladle')
def build_tombo():
    bar = cyl(WOOD_DARK, .016, .016, .46, (0, 0, .016), rot=(0, math.radians(90), 0), verts=16)
    stick = cyl(WOOD_DARK, .014, .014, .4, (0, -.2, .016), rot=(math.radians(90), 0, 0), verts=16)
    for o in (bar, stick): bevel(o, .006, 3)
    return join([bar, stick], 'tombo')
def build_turner():
    blade = cube(CREAM, (.3, .18, .02), (0, 0, .01)); bevel(blade, .015, 4)
    hd = cyl(PINK, .02, .02, .34, (.3, 0, .035), rot=(0, math.radians(78), 0), verts=16); bevel(hd, .01, 3)
    return join([blade, hd], 'turner')
def build_bag():
    cone = cyl(WHITE, .08, .0, .32, (0, 0, .17)); bevel(cone, .02, 4)
    top = sphere(WHITE, .07, (0, 0, .33), (1, 1, .5))
    tip = cyl(STEEL, .034, .014, .07, (0, 0, .01)); bevel(tip, .005, 2)
    return join([cone, top, tip], 'bag')
def build_bottle():
    body = cyl(WHITE, .055, .055, .22, (0, 0, .11)); bevel(body, .02, 4)
    cap = sphere(WHITE, .055, (0, 0, .22), (1, 1, .5))
    tip = cyl(WHITE, .03, .012, .07, (0, 0, .28))
    return join([body, cap, tip], 'bottle')

# ---------- bowl + fruit ----------
def build_bowl():
    pts = [(.02, 0), (.12, .01), (.17, .06), (.2, .13), (.21, .15), (.19, .15), (.18, .13), (.15, .06), (.1, .03), (.02, .03)]
    ob = spin_profile(pts, 'bowl', WHITE); subsurf(ob, 1); return ob
def build_strawberry():
    s = sphere(STRAW, .085, (0, 0, 0), seg=40); bpy.ops.object.mode_set(mode='OBJECT')
    me = s.data
    for v in me.vertices:  # unit sphere coordinates (object scale = .085)
        f = (v.co.z + 1) / 2  # 0 bottom .. 1 top(tip)
        k = 1 - .62 * max(0, f - .25) ** 1.4; v.co.x *= k; v.co.y *= k; v.co.z *= 1.25
    parts = [s]
    # cut lengthwise (keep y<0 half), fill the cut with the face texture
    bpy.ops.object.select_all(action='DESELECT'); s.select_set(True); bpy.context.view_layer.objects.active = s
    s.data.materials.append(STRAW_FACE)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bisect(plane_co=(0, 0, 0), plane_no=(0, 1, 0), clear_outer=True, use_fill=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    for poly in s.data.polygons:
        if abs(poly.normal.y) > .95: poly.material_index = 1
    bm = bmesh.new(); bm.from_mesh(s.data); uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        if f.material_index == 1:
            for l in f.loops: l[uvl].uv = (l.vert.co.x * .5 + .5, l.vert.co.z / 1.25 * .5 + .5)
    bm.to_mesh(s.data); bm.free()
    for i in range(30):
        zu = random.uniform(-.85, .95); phi = random.uniform(math.pi, 2 * math.pi)
        f = (zu + 1) / 2; k = 1 - .62 * max(0, f - .25) ** 1.4; rr = math.sqrt(max(0, 1 - zu * zu)) * k * .085
        pos = Vector((math.cos(phi) * rr, math.sin(phi) * rr, zu * 1.25 * .085))
        n = Vector((math.cos(phi) * rr, math.sin(phi) * rr, zu * .085 * .6)).normalized()
        sd = sphere(SEED, .0045, pos + n * .001, (1, 1, 1.5), seg=10); sd.rotation_euler = n.to_track_quat('Z', 'Y').to_euler(); parts.append(sd)
    for i in range(5):
        a = i / 5 * 2 * math.pi
        if math.sin(a) > .05: continue
        lf = sphere(LEAF_DARK, .04, (math.cos(a) * .035, math.sin(a) * .035, -.095), (1.5, .55, .22)); lf.rotation_euler = (0, math.radians(-25), a); parts.append(lf)
    ob = join(parts, 'fruit_ichigo'); ob.rotation_euler = (math.radians(-90), 0, 0); ob.location = (0, 0, .002)
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob
def build_slice(name, r, h, side_m, face_m):
    side = cyl(side_m, r, r, h, (0, 0, h / 2), fill='NOTHING'); bevel(side, .006, 2)
    bpy.ops.mesh.primitive_circle_add(radius=r, vertices=48, fill_type='NGON', location=(0, 0, h + .001)); top = bpy.context.active_object; top.data.materials.append(face_m); disc_uv(top)
    bpy.ops.mesh.primitive_circle_add(radius=r, vertices=48, fill_type='NGON', location=(0, 0, -.001), rotation=(math.pi, 0, 0)); bot = bpy.context.active_object; bot.data.materials.append(face_m); disc_uv(bot)
    return join([side, top, bot], name)
def build_mikan():
    seg = sphere(MIKAN, .1, (0, 0, .05), (1.15, .6, .5), seg=36)
    skin = sphere(ORANGE_SKIN, .1, (0, 0, .05), (1.17, .62, .52), seg=36)
    # keep only the outer (back) half of the skin by scaling - cheap membrane look
    skin.scale = (1.17 * .1, .62 * .1, .52 * .1); skin.location = (0, .012, .05)
    return join([seg, skin], 'fruit_mikan')
def build_blueberry():
    b = sphere(BLUE, .055, (0, 0, .055), seg=36)
    bloom = sphere(BLUE_BLOOM, .0555, (0, 0, .055), seg=36); bloom.data.materials[0].blend_method = 'BLEND'
    bloom.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = .22
    parts = [b, bloom]
    for i in range(5):
        a = i / 5 * 2 * math.pi
        parts.append(cyl(DARK, .006, .0, .02, (math.cos(a) * .012, math.sin(a) * .012, .108), verts=8))
    return join(parts, 'fruit_blueberry')
def build_chip():
    parts = []
    for i in range(5):
        a = i * 1.26
        parts.append(sphere(CHOC, .028, (math.cos(a) * .06, math.sin(a) * .06, .02), (1.2, 1, .7), seg=16))
    return join(parts, 'fruit_chip')

# ---------- cat ----------
def build_cat():
    P = []
    P.append(sphere(FUR, .36, (0, 0, .2), (1, .9, .8), seg=48))
    P.append(sphere(FUR, .36, (0, 0, .66), (1.05, 1, .92), seg=48))
    P.append(sphere(FUR_SPOT, .17, (.22, -.12, .84), (1.1, 1, .7), seg=32))
    for sg in (-1, 1):
        ear = cyl(FUR, .1, .0, .2, (sg * .26, 0, .96), rot=(0, sg * .5, 0), verts=24); bevel(ear, .02, 3); P.append(ear)
        P.append(cyl(BLUSH, .055, .0, .12, (sg * .255, -.02, .95), rot=(0, sg * .5, 0), verts=16))
        P.append(sphere(DARK, .04, (sg * .13, -.33, .68), seg=24))
        P.append(sphere(WHITE, .012, (sg * .13 - .012, -.37, .695), seg=12))
        P.append(sphere(BLUSH, .06, (sg * .25, -.28, .58), (1, .5, .6), seg=20))
        P.append(sphere(FUR, .11, (sg * .24, -.3, .32), (1, .8, .8), seg=28))
    P.append(sphere(NOSE, .025, (0, -.36, .62), (1.3, .8, .8), seg=16))
    P.append(torus(PINK, .22, .04, (0, 0, .42)))
    hat = cyl(WHITE, .22, .24, .12, (0, 0, 1.0)); bevel(hat, .02, 3); P.append(hat)
    P.append(sphere(WHITE, .26, (0, 0, 1.1), (1, 1, .8), seg=40)); P.append(sphere(WHITE, .14, (.14, -.02, 1.2), seg=32)); P.append(sphere(WHITE, .12, (-.15, -.04, 1.18), seg=32))
    return join(P, 'cat')

# ---------- sign (cat face + mini crepe, no text) ----------
def build_sign():
    P = []
    base = cube(PINK, (1.05, .06, .7), (0, 0, .35)); bevel(base, .03, 5); P.append(base)
    inner = cube(CREAM, (.92, .02, .58), (0, -.035, .35)); bevel(inner, .015, 4); P.append(inner)
    head = sphere(FUR, .13, (-.22, -.06, .36), (1.1, .5, .95), seg=32); P.append(head)
    for sg in (-1, 1):
        P.append(cyl(FUR, .045, .0, .09, (-.22 + sg * .1, -.06, .47), rot=(0, sg * .4, 0), verts=16))
        P.append(sphere(DARK, .016, (-.22 + sg * .05, -.1, .37), seg=12))
        P.append(sphere(BLUSH, .025, (-.22 + sg * .09, -.1, .33), (1, .4, .7), seg=12))
    P.append(sphere(NOSE, .012, (-.22, -.11, .345), seg=10))
    cone = cyl(PINK, .09, .0, .24, (.22, -.06, .27), rot=(math.pi, 0, 0)); P.append(cone)
    for i, (x, z, r) in enumerate([(-.05, .41, .045), (.05, .41, .045), (0, .47, .045), (-.025, .52, .035), (.025, .52, .035), (0, .57, .03)]):
        P.append(sphere(WHITE, r, (.22 + x, -.07, z), seg=20))
    P.append(sphere(STRAW, .03, (.22, -.09, .6), seg=16))
    return join(P, 'sign')

# ---------- shelf props ----------
def build_cream():
    pts = []
    for i in range(0, 41):
        t = i / 40; r = .058 * (1 - t) ** .65 * (1 + .22 * math.sin(t * math.pi * 5.5)) + .002
        pts.append((r, t * .075))
    ob = spin_profile(pts, 'cream', WHIP, steps=40); return ob
def build_plant():
    P = [cyl(POT, .11, .14, .22, (0, 0, .11))]; bevel(P[0], .02, 3)
    for i in range(10):
        a = i * .7; P.append(sphere(LEAF if i % 2 else LEAF_DARK, .1, (math.cos(a) * .16, math.sin(a) * .11, .3 + (i % 3) * .07), (1.3, .9, .55), seg=20))
    return join(P, 'plant')
def build_jar():
    body = cyl(WHITE, .12, .12, .3, (0, 0, .15)); bevel(body, .02, 4)
    lid = cyl(PINK, .13, .13, .06, (0, 0, .33)); bevel(lid, .015, 3)
    return join([body, lid], 'jar')

objs = [build_maker(), build_tray(), build_ladle(), build_tombo(), build_turner(), build_bag(), build_bottle(), build_bowl(),
        build_strawberry(), build_slice('fruit_banana', .085, .05, BANANA_SIDE, BANANA_FACE), build_slice('fruit_kiwi', .095, .05, KIWI_SIDE, KIWI_FACE),
        build_mikan(), build_blueberry(), build_chip(), build_cream(), build_cat(), build_sign(), build_plant(), build_jar()]
for ob in objs:
    ob.location = (0, 0, 0) if ob.name not in ('maker',) else ob.location
for ob in bpy.data.objects:
    if ob.type == 'MESH': smooth(ob)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_apply=True, export_yup=True, export_materials='EXPORT', export_image_format='AUTO', export_texcoords=True, export_normals=True, use_selection=True)
print('EXPORTED', OUT, [o.name for o in objs])

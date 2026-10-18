"""CLI Tortoises: check a rigged tortoise against the game's rig spec, then export it for the game.

HOW TO USE (Blender 3.6 or newer)
  1. Open your tortoise's .blend, and select its armature (or have only one armature in the scene).
  2. Scripting tab > Text Editor > Open this file > Run Script.
  3. It checks the rig, copies each action's `hit` marker into the action so the game gets it, and exports
     <your .blend's name>.glb beside the .blend with the settings the game needs. The report prints to the
     system console (Window > Toggle System Console on Windows; the terminal you started Blender from on Mac and
     Linux) and a summary shows in the status bar.
  4. Drop the .glb on the game's Rig Lab (game.html#riglab): it plays every clip, shows where the hit lands, and
     puts the NFT traits' colours and gear on your tortoise. "Ride it" takes it out onto the island.
  Without opening Blender's window (a script, a batch of files, an AI agent):
       blender -b your.blend --python cli_tortoises_rig.py
     prints the same report, exports <your .blend's name>.glb beside the .blend, and exits 1 if the rig fails.

THE SPEC (the Rig Lab checks the same things and says them the same way)
  - One armature. At most 60 bones, and at most 4 bone weights on any vertex (the exporter keeps the 4 heaviest).
  - Blender's Z up, the tortoise facing -Y, transforms applied (rotation 0, scale 1). Any size: the game sizes it
    to its own tortoise by the shell's width.
  - One action per clip, named:
        idle, walk                      needed; they loop
        run                             loops (without it, walking just speeds up)
        attack, hurt, death, celebrate  play once
        shell_in, shell_out             play once (into the shell, and back out)
        special_<name>                  play once: special_spin is the spin attack, and any others are kept for
                                        the battles' special moves
    30 fps, in place (no root motion: the game moves the tortoise), and a looping clip's last frame the same as
    its first.
  - On attack and every special_*, a pose marker named `hit` (Action editor > Marker > Add Marker, with "Show Pose
    Markers" on) on the frame the blow lands. Damage, sparks and the shake happen there.
  - Socket bones, for the NFT gear (each sits where the gear should sit, pointing up, and needn't deform):
        socket_head                     centre of the head (hats, bandanas)
        socket_neck                     base of the neck (chains, scarves)
        socket_shell                    top of the shell (the saddle; shell props)
        socket_wrist_L, socket_wrist_R  the front wrists (watches)
        socket_foot_FL, socket_foot_FR, socket_foot_BL, socket_foot_BR   the soles (footwear, claws)
    A socket bone's custom property `fit` (a number) scales the gear on it, if it comes out too big or small.
  - Material slots the traits colour: skin, rim, belly, eyes, and either shell (tinted the trait's shell colour)
    or shell_art (the NFT's own shell art painted on through its UVs: U around the dome, V from the rim at 0 to the
    top at 1). The traits colour skin, rim, belly and shell: a texture on them is kept and tinted, so paint those
    textures in light greys (a trait with spots puts its spots on the skin in place of the texture).
  - About 10-20k triangles for your tortoise.

THE ISLAND'S CHARACTERS
  A character's rig says which character it is with a custom property on its armature object, `cli_kind`
  (Object properties > Custom Properties; no property is a tortoise), and is checked against that character's
  spec: the same rules for the armature, the axes, 30 fps, in place, loops and `hit` markers, with its own clips,
  sockets and slots. The game paints every slot in its own colour, in the island's drawn look.
    cli_kind = dr_shrimp    Dr. Bubba Gump Shrimp, the pistol shrimp at the cleaning station (Shell No)
        clips    idle, talk (needed; they loop) · walk, dance (loop) · aim, snap, celebrate, wave (once): aim
                 brings his snapping claw to bear and cocks it (the game holds its last frame), and snap starts
                 from there
        hit      on snap: the frame the claw shuts, when the bubble leaves it (the clam comes off when it lands)
        sockets  socket_head (his head mirror), socket_snap (the snapping claw's muzzle: the bubble leaves from
                 here), socket_claw_L, socket_claw_R (what each claw holds)
        slots    lens (the head mirror's glass, shown once you've brought him sea glass), probe (the urchin-spine
                 probe in his small claw, shown once you've brought him one), glint (the shine on his eyes and
                 mirror: drawn unlit, with no ink)
        budget   about 5-15k triangles
    app/scripts/dr_shrimp.py builds him to it, and is the worked example.
"""
import bpy, json, math, os, sys
from mathutils import Vector

MAX_BONES, MAX_WEIGHTS = 60, 4
# the kinds of rig the game takes, each its own spec: an NFT tortoise (a rig with no `cli_kind`), and the island's
# characters. `front` and `back` are the bones that say which way it faces (the first of each it has)
KINDS = {
    "tortoise": dict(
        who="your tortoise", needed=("idle", "walk"), wanted=("run", "attack", "hurt", "death", "celebrate", "shell_in", "shell_out"),
        loops=("idle", "walk", "run"), hits=lambda n: n == "attack" or n.startswith("special_"), specials=True,
        sockets=("socket_head", "socket_neck", "socket_shell", "socket_wrist_L", "socket_wrist_R",
                 "socket_foot_FL", "socket_foot_FR", "socket_foot_BL", "socket_foot_BR"),
        slots=("skin", "rim", "belly", "eyes"), shell=True, tris=(10000, 20000), front=("socket_head", "head"), back=("socket_shell",)),
    "dr_shrimp": dict(
        who="Dr. Shrimp", needed=("idle", "talk"), wanted=("walk", "dance", "aim", "snap", "celebrate", "wave"),
        loops=("idle", "walk", "dance", "talk"), hits=lambda n: n == "snap", specials=False,
        sockets=("socket_head", "socket_snap", "socket_claw_L", "socket_claw_R"),
        slots=("lens", "probe", "glint"), shell=False, tris=(5000, 15000), front=("socket_head", "head"), back=("tail", "body", "root")),
}
SLOT_WHY = {"lens": "the head mirror never gets its glass", "probe": "he never holds his probe", "glint": "the eyes have no shine"}


def kind_of(arm):
    """which spec a rig is checked against: its armature's `cli_kind`, or a tortoise"""
    k = str(arm.get("cli_kind", "tortoise")) if arm is not None else "tortoise"
    return k if k in KINDS else "tortoise"


# ---------------------------------------------------------------- reading an action, old Blender and new
def fcurves(act):
    """an action's F-curves: Blender 4.4+ keeps them in layers and slots, older Blenders on the action itself"""
    if not hasattr(act, "layers") or (hasattr(act, "is_action_layered") and not act.is_action_layered and hasattr(act, "fcurves")):
        return list(getattr(act, "fcurves", []))
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            bags = getattr(strip, "channelbags", None)
            if bags is not None:
                for cb in bags: out += list(cb.fcurves)
            else:
                for slot in act.slots:
                    cb = strip.channelbag(slot)
                    if cb: out += list(cb.fcurves)
    return out


def frame_range(act):
    a, b = act.frame_range
    return int(round(a)), int(round(b))


# ---------------------------------------------------------------- the check
class Report:
    def __init__(s): s.rows = []
    def ok(s, text): s.rows.append(("ok", text))
    def warn(s, text): s.rows.append(("warn", text))
    def fail(s, text): s.rows.append(("fail", text))
    def info(s, text): s.rows.append(("info", text))
    @property
    def failed(s): return any(k == "fail" for k, _ in s.rows)
    def text(s):
        mark = {"ok": "  ok  ", "warn": " WARN ", "fail": " FAIL ", "info": "  --  "}
        return "\n".join(mark[k] + t for k, t in s.rows)
    def summary(s):
        n = {k: sum(1 for kk, _ in s.rows if kk == k) for k in ("ok", "warn", "fail")}
        return f"CLI Tortoises rig: {n['ok']} ok, {n['warn']} to look at, {n['fail']} to fix"


def find_armature(context):
    sel = [o for o in context.selected_objects if o.type == "ARMATURE"]
    if len(sel) == 1: return sel[0]
    arms = [o for o in context.scene.objects if o.type == "ARMATURE"]
    return arms[0] if len(arms) == 1 else None


def rig_meshes(arm):
    return [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]


def rig_actions(arm):
    """the actions that animate this armature: every action whose curves name its bones (or that's on its tracks)"""
    names = {b.name for b in arm.data.bones}
    out = []
    for act in bpy.data.actions:
        if any(fc.data_path.startswith('pose.bones["') and fc.data_path.split('"')[1] in names for fc in fcurves(act)): out.append(act)
    return out


def check(context=None):
    context = context or bpy.context
    R = Report(); arm = find_armature(context)
    if arm is None:
        R.fail("No armature found: select the tortoise's armature (or keep only one in the scene)."); return R, None
    R.ok(f"Armature: {arm.name}")
    kind = kind_of(arm); S = KINDS[kind]
    if "cli_kind" in arm and str(arm["cli_kind"]) not in KINDS:
        R.warn(f"cli_kind is {arm['cli_kind']}, which the game doesn't know ({', '.join(KINDS)}): checked as a tortoise")
    elif kind != "tortoise": R.info(f"A character's rig: {S['who']} (cli_kind {kind})")
    bones = arm.data.bones; deform = [b for b in bones if b.use_deform]
    (R.ok if len(bones) <= MAX_BONES else R.warn)(f"{len(bones)} bones ({len(deform)} deforming); at most {MAX_BONES} keeps phones happy")
    if any(abs(v) > 1e-4 for v in arm.rotation_euler) or any(abs(v - 1) > 1e-4 for v in arm.scale):
        R.warn("The armature has rotation or scale: apply them (Ctrl+A > All Transforms) so the export matches what you see")
    meshes = rig_meshes(arm)
    if not meshes: R.fail("No mesh is skinned to the armature (an Armature modifier pointing at it)")
    tris, over, slots = 0, 0, set()
    for o in meshes:
        me = o.data; me.calc_loop_triangles(); tris += len(me.loop_triangles)
        over += sum(1 for v in me.vertices if sum(1 for g in v.groups if g.weight > 1e-4) > MAX_WEIGHTS)
        slots |= {(m.name.split(".")[0].lower() if m else "") for m in me.materials}
        if any(abs(v) > 1e-4 for v in o.rotation_euler) or any(abs(v - 1) > 1e-4 for v in o.scale):
            R.warn(f"Mesh {o.name} has rotation or scale: apply them")
    if meshes:
        (R.ok if over == 0 else R.warn)(f"{over} vertices with more than {MAX_WEIGHTS} weights" + ("" if over == 0 else " (the export keeps the 4 heaviest; Weights > Limit Total to fix)"))
        (R.ok if tris <= S["tris"][1] else R.warn)(f"{tris} triangles (about {S['tris'][0] // 1000}-{S['tris'][1] // 1000}k for {S['who']})")
    # facing -Y: the head is in front of the shell (a character's, in front of its tail)
    head = next((bones[n] for n in S["front"] if n in bones), None)
    back = next((bones[n] for n in S["back"] if n in bones), None)
    if head and back:
        (R.ok if head.head_local.y < back.head_local.y else R.fail)("Facing -Y (the head is toward -Y)" if head.head_local.y < back.head_local.y else f"The head is toward +Y: turn {'the tortoise' if kind == 'tortoise' else S['who']} to face -Y")
    for s in S["sockets"]:
        if s in bones: R.ok(f"Socket {s}")
        else: R.warn(f"No {s}: that gear won't show" if kind == "tortoise" else f"No {s}: nothing can be held there")
    for s in S["slots"]:
        (R.ok if s in slots else R.warn)(f"Material slot {s}" if s in slots else f"No material slot named {s}: " + ("it won't take the traits' colour" if kind == "tortoise" else SLOT_WHY.get(s, "it keeps its own colour")))
    if S["shell"]:
        if "shell" in slots or "shell_art" in slots: R.ok("Material slot " + ("shell_art (the NFT shell art goes on through its UVs)" if "shell_art" in slots else "shell"))
        else: R.warn("No material slot named shell or shell_art: the shell won't take the traits' colour")
    # the clips
    acts = {a.name: a for a in rig_actions(arm)}
    fps = context.scene.render.fps / context.scene.render.fps_base
    (R.ok if abs(fps - 30) < 0.01 else R.warn)(f"Scene at {fps:g} fps" + ("" if abs(fps - 30) < 0.01 else " (the clips are made at 30)"))
    for c in S["needed"]:
        (R.ok if c in acts else R.fail)(f"Clip {c}" if c in acts else f"No action named {c} (it's needed)")
    for c in S["wanted"]:
        (R.ok if c in acts else R.warn)(f"Clip {c}" if c in acts else f"No action named {c}")
    specials = sorted(n for n in acts if n.startswith("special_")) if S["specials"] else []
    if S["specials"]: R.info("Specials: " + (", ".join(specials) if specials else "none yet (special_spin is the spin attack)"))
    known = set(S["needed"]) | set(S["wanted"]) | set(specials)
    for n in sorted(set(acts) - known): R.info(f"Action {n} isn't one of the game's clips: it's exported but nothing plays it")
    root = next((b for b in bones if b.parent is None), None)
    for name, act in acts.items():
        a, b = frame_range(act); curves = fcurves(act)
        if name in S["loops"]:
            bad = [fc for fc in curves if abs(fc.evaluate(a) - fc.evaluate(b)) > 1e-3]
            (R.ok if not bad else R.warn)(f"{name} loops (first frame = last)" if not bad else f"{name}: the last frame isn't the first on {len(bad)} channels, so the loop will pop")
        if root:
            # how far the root wanders over the ground (its keys are in its own axes: turned into the armature's, Z
            # up, only X and Y count; a hop is fine)
            loc = {fc.array_index: fc for fc in curves if fc.data_path == f'pose.bones["{root.name}"].location'}
            if loc:
                rot = root.matrix_local.to_3x3()
                at = lambda f: rot @ Vector(tuple(loc[i].evaluate(f) if i in loc else 0.0 for i in range(3)))
                p0 = at(a); drift = max(math.hypot(*(at(f) - p0)[:2]) for f in range(a, b + 1))
                if drift > 0.05: R.warn(f"{name}: the root bone travels {drift:.2f} m over the ground; make it in place (the game moves {'the tortoise' if kind == 'tortoise' else S['who']})")
        if S["hits"](name):
            hit = [m for m in act.pose_markers if m.name.lower() == "hit"]
            (R.ok if hit else R.warn)(f"{name}: hit on frame {hit[0].frame}" if hit else f"{name}: no `hit` pose marker (the game will guess 40% of the way through)")
    return R, arm


# ---------------------------------------------------------------- markers into the actions, and the export
def bake_markers(arm, fps=None):
    """each action's pose markers, as seconds from its first frame, into its custom properties (they become the
    clip's glTF extras, which the game reads): `hit` for the hit frame, and `markers` for all of them"""
    fps = fps or bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    for act in rig_actions(arm):
        a, _ = frame_range(act); ms = {m.name: round((m.frame - a) / fps, 4) for m in act.pose_markers}
        if ms: act["markers"] = json.dumps(ms)
        if "hit" in {k.lower() for k in ms}: act["hit"] = next(v for k, v in ms.items() if k.lower() == "hit")
        act["fps"] = round(fps, 3)


def export(arm, path):
    """the .glb the game reads: Y up, every action its own clip from time 0, sampled at the scene's fps, at most 4
    weights, the custom properties as extras, and only the armature and what's skinned to it"""
    for o in bpy.context.selected_objects: o.select_set(False)
    arm.select_set(True)
    for o in rig_meshes(arm): o.select_set(True)
    for o in arm.children_recursive if hasattr(arm, "children_recursive") else arm.children: o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    want = dict(filepath=path, export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
                export_animations=True, export_animation_mode="ACTIONS", export_anim_slide_to_zero=True,
                export_force_sampling=True, export_frame_step=1, export_extras=True, export_skins=True,
                export_influence_nb=MAX_WEIGHTS, export_def_bones=False, export_rest_position_armature=True,
                export_reset_pose_bones=True, export_anim_single_armature=True, export_materials="EXPORT")
    have = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    bpy.ops.export_scene.gltf(**{k: v for k, v in want.items() if k in have})
    return path


def main():
    R, arm = check()
    print("\n" + R.summary() + "\n" + R.text() + "\n")
    if arm is None or R.failed:
        msg = R.summary() + ": not exported (see the console)"
    else:
        bake_markers(arm)
        blend = bpy.data.filepath
        path = os.path.splitext(blend)[0] + ".glb" if blend else os.path.join(os.path.expanduser("~"), kind_of(arm).replace("_", "-") + ".glb")
        export(arm, path)
        msg = R.summary() + f": exported {path}"
    print(msg)
    def draw(self, _ctx):
        for k, t in R.rows:
            if k in ("warn", "fail"): self.layout.label(text=t, icon="ERROR" if k == "fail" else "INFO")
        self.layout.label(text=msg)
    # run headless there's no window for the pop-up: it ends instead with a code a script can read, 0 exported, 1 not
    if bpy.app.background:
        if arm is None or R.failed: sys.exit(1)
        return
    try: bpy.context.window_manager.popup_menu(draw, title="CLI Tortoises rig", icon="ARMATURE_DATA")
    except Exception: pass


if __name__ == "__main__":
    main()

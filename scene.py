import bpy
import random
import math

DATA = {
    "Mail": 2301,
    "JobCreator": 2754,
    "JobReadinessChecker": 2841,
    "InfraFailureAnalysis": 5033,
    "Orchestrator": 5058,
    "DropLocationScanner": 8977,
    "TestFailureAnalysis": 12174,
}

SCALE_FACTOR = 2
FRAME_PAUSE = 24
FRAME_MOVE = 36
DEFAULT_SEGMENTS = 64
DEFAULT_RING_COUNT = 32


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def create_noise_material():
    material = bpy.data.materials.new(name=f"DynamicNoise")
    material.use_nodes = True

    material.node_tree.nodes.clear()

    noise_node = material.node_tree.nodes.new("ShaderNodeTexNoise")
    color_ramp = material.node_tree.nodes.new("ShaderNodeValToRGB")
    bsdf_node = material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    output_node = material.node_tree.nodes.new("ShaderNodeOutputMaterial")

    material.node_tree.links.new(noise_node.outputs["Fac"], color_ramp.inputs["Fac"])
    material.node_tree.links.new(color_ramp.outputs["Color"], bsdf_node.inputs["Base Color"])
    material.node_tree.links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    noise_node.inputs["Scale"].default_value = random.uniform(5.0, 20.0)
    noise_node.inputs["Detail"].default_value = random.uniform(2.0, 100.0)
    noise_node.inputs["Roughness"].default_value = random.uniform(0.3, 0.8)

    color_ramp.color_ramp.elements[0].color = (
        random.random(), random.random(), random.random(), 1
    )
    color_ramp.color_ramp.elements[1].color = (
        random.random(), random.random(), random.random(), 1
    )
    color_ramp.color_ramp.interpolation = 'EASE'

    return material


def create_emissive_material():
    material = bpy.data.materials.new(name="Emission")
    material.use_nodes = True

    material.node_tree.nodes.clear()

    emission_node = material.node_tree.nodes.new("ShaderNodeEmission")
    output_node = material.node_tree.nodes.new("ShaderNodeOutputMaterial")
    material.node_tree.links.new(emission_node.outputs["Emission"], output_node.inputs["Surface"])

    emission_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    emission_node.inputs["Strength"].default_value = 1.0

    return material


def add_sphere(name, scale, location):
    bpy.ops.mesh.primitive_uv_sphere_add(
        location=location,
        segments=DEFAULT_SEGMENTS,
        ring_count=DEFAULT_RING_COUNT,
    )

    sphere = bpy.context.object
    sphere.name = name
    sphere.scale = (scale, scale, scale)
    sphere.location[2] = scale
    bpy.ops.object.shade_smooth()

    sphere.data.materials.append(create_noise_material())

    return sphere


def add_text(location, text_body, scale, is_emissive=False):
    bpy.ops.object.text_add(location=location)

    text = bpy.context.object
    text.data.body = text_body
    text.data.size = scale * 0.25
    text.data.align_x = 'CENTER'
    text.rotation_euler = (1.5708, 0, 0)

    if is_emissive:
        text.data.materials.append(create_emissive_material())

    return text


def create_camera(spheres):
    first_radius = spheres[0].scale[0]

    bpy.ops.object.camera_add(location=(spheres[0].location[0] + first_radius, -first_radius * 10, first_radius * 1.3))
    camera = bpy.context.object
    camera.rotation_euler = (1.5708, 0, 0)
    bpy.context.scene.camera = camera

    return camera


def create_lights(spheres, camera):
    bpy.ops.object.light_add(type='SUN', location=(
        spheres[0].scale[0] * -10, spheres[0].scale[0] * -10, spheres[0].scale[0] * 10
    ))
    sun1 = bpy.context.object
    sun1.rotation_euler = (0, math.radians(-45), math.radians(15))
    sun1.data.energy = 2.0

    bpy.ops.object.light_add(type='SUN', location=(
        camera.location.x, camera.location.y, camera.location.z * 2
    ))
    sun2 = bpy.context.object
    sun2.rotation_euler = (math.radians(75), 0, math.radians(-15))
    sun2.data.energy = 0.2
    sun2.data.use_shadow = False


def animate_camera(camera, spheres):
    current_frame = 1

    for sphere in spheres:
        sphere_radius = sphere.scale[0]
        camera.location = (sphere.location[0], -sphere_radius * 10, sphere_radius * 1.3)
        camera.keyframe_insert(data_path="location", frame=current_frame)

        current_frame += FRAME_PAUSE
        camera.keyframe_insert(data_path="location", frame=current_frame)

        current_frame += FRAME_MOVE

    bpy.context.scene.frame_end = current_frame

    for curve in camera.animation_data.action.fcurves:
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = 'BEZIER'


def setup_background(image_path, x_position):
    image = bpy.data.images.load(image_path)

    aspect_ratio = image.size[0] / image.size[1]
    plane_width = x_position * 2.5
    plane_height = plane_width / aspect_ratio

    bpy.ops.mesh.primitive_plane_add(location=(
        plane_width / 2 - plane_width * 0.1, x_position * 3, plane_height / 2 - plane_height * 0.1
    ))
    plane = bpy.context.object
    plane.rotation_euler = (math.radians(-90), 0, 0)
    plane.scale = (plane_width, plane_height, 1)

    material = bpy.data.materials.new(name="BackgroundImage")
    material.use_nodes = True

    material.node_tree.nodes.clear()

    tex_image = material.node_tree.nodes.new(type="ShaderNodeTexImage")
    output = material.node_tree.nodes.new(type="ShaderNodeOutputMaterial")
    bsdf = material.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")

    tex_image.image = image
    material.node_tree.links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])
    material.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    plane.data.materials.append(material)


clear_scene()

max_value = max(DATA.values())

x_position = 0
spheres = []

for name, value in DATA.items():
    scale = (value / max_value) * SCALE_FACTOR
    if spheres:
        previous_radius = spheres[-1].scale[0]
        x_position += previous_radius + scale + previous_radius

    sphere = add_sphere(name, scale, (x_position, 0, 0))
    add_text((sphere.location[0], sphere.location[1], sphere.location[2] + scale * 1.35), name, scale, is_emissive=True)
    add_text((sphere.location[0], sphere.location[1], sphere.location[2] - scale * 1.3), f"{value} LoC", scale, is_emissive=True)

    spheres.append(sphere)

camera = create_camera(spheres)
create_lights(spheres, camera)
setup_background("c:/images/stars-background.jpg", x_position)
animate_camera(camera, spheres)

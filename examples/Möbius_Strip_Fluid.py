from math import pi
from nodetree_script import *
from nodetree_script.api.dynamic.shader import *


@materialtree
def fluid():
    base_color = (0.5,0.5,1,1)
    time_value = scripted_expression("frame / 250")
    time_value = pingpong(time_value)
    noise_color = texture_coordinate().generated.noise_texture(noise_dimensions=NoiseTexture.NoiseDimensions._4D, w=time_value).color
    norm =  bump(normal=noise_color,distance=0.1)
    shader = glass_bsdf(normal=norm,color=base_color,roughness=0.25)

    return shader


from nodetree_script.api.dynamic.geometry import *
@geometrytree
def mobius_strip(half_twists: Int = 1):
    Nx = 50
    Ny = 50
    mesh, uv = grid(vertices_x=Nx,vertices_y=Ny)
    u,v = uv.x, uv.y
    time_value = scripted_expression("frame / 250")
    time_value = pingpong(time_value)
    u_ = pingpong(u)
    v_ = pingpong(v)
    offset = (combine_xyz(x=u_,y=v_,z=time_value).noise_texture(noise_dimensions=NoiseTexture.NoiseDimensions._3D).color - 0.5)* 0.1

    n = half_twists
    u = u * 2 * pi
    v = (v * 2 - 1) * 0.5
    x = ( 1 + v/2 * cos(n*u/2) ) * cos(u)
    y = ( 1 + v/2 * cos(n*u/2) ) * sin(u)
    z = v/2 * sin(n*u/2)

    mesh = mesh.set_position(position=combine_xyz(x=x,y=y,z=z)).set_position(position=position(),offset=offset).merge_by_distance()
    mesh = mesh.set_material(material=fluid).set_shade_smooth()

    return mesh
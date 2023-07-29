use std::path::PathBuf;

use bevy::render::camera::{Camera as CameraDetails, RenderTarget};
use bevy::render::mesh::VertexAttributeValues;
use bevy::render::render_resource::{
    AddressMode, Extent3d, SamplerDescriptor, TextureDescriptor, TextureDimension, TextureFormat,
    TextureUsages,
};
use bevy::{app::AppExit, prelude::*, window::WindowResolution, winit::WinitSettings};
use bevy_image_export::{
    ImageExportBundle, ImageExportPlugin, ImageExportSettings, ImageExportSource,
};
use rand::{distributions::Uniform, prelude::*};

#[derive(Component)]
struct Camera;

#[derive(Component)]
struct Ground;

#[derive(Component)]
struct Pad;

#[derive(Resource)]
struct Textures {
    ground: Vec<Handle<Image>>,

    bottle_dropoff: Handle<Image>,
    medkit_dropoff: Handle<Image>,
    smores_dropoff: Handle<Image>,
    bottle_pickup: Handle<Image>,
    medkit_pickup: Handle<Image>,
    smores_pickup: Handle<Image>,

    pad_mesh: Handle<Mesh>,
    ground_mesh: Handle<Mesh>,
}

#[derive(Resource)]
struct Counter {
    current: u32,
    max: u32,
}

const MAX_ALT: f32 = 50.;
const MIN_ALT: f32 = 8.0;
const FOV_DEG: f32 = 69_f32;
const PAD_SIZE: f32 = 4.0;
const MAX_CAM_SWAY_DEG: f32 = 10.;
// Gives better data for when the drone is yawed improperly
const MAX_CAM_SWAY_DEG_ROLL: f32 = 45.;
const NUM_DATA_POINTS: u32 = 120;

fn main() {
    let export_plugin = ImageExportPlugin::default();
    let export_threads = export_plugin.threads.clone();

    App::new()
        .insert_resource(WinitSettings {
            return_from_run: true,
            ..Default::default()
        })
        .insert_resource(Counter {
            current: 1,
            max: NUM_DATA_POINTS,
        })
        .add_plugins(
            DefaultPlugins
                .set(WindowPlugin {
                    primary_window: Some(Window {
                        resolution: WindowResolution::new(416., 416.),
                        ..Default::default()
                    }),
                    ..Default::default()
                })
                .set(ImagePlugin {
                    default_sampler: SamplerDescriptor {
                        address_mode_u: AddressMode::Repeat,
                        address_mode_v: AddressMode::Repeat,
                        address_mode_w: AddressMode::Repeat,
                        ..Default::default()
                    },
                }),
        )
        .add_plugin(export_plugin)
        .add_startup_system(setup)
        .add_system(simulate_frame)
        .run();

    // This line is optional but recommended.
    // It blocks the main thread until all image files have been saved successfully.
    export_threads.finish();

    println!("Done! Cleaning up...");
    let mut cleaned_up: u32 = 0;

    // Clean up images with no labels
    for image in std::fs::read_dir("out/images").unwrap() {
        let image_path = image.unwrap().path();
        let image_no_ext = image_path.file_stem().unwrap().to_string_lossy();
        if !PathBuf::from(format!("out/labels/{image_no_ext}.txt")).exists() {
            std::fs::remove_file(image_path).unwrap();
            cleaned_up += 1;
        }
    }

    /*

    // Clean up the last label, frame isn't gonna generate
    std::fs::remove_file(
        std::fs::read_dir("out/labels")
            .unwrap()
            .into_iter()
            .last()
            .unwrap()
            .unwrap()
            .path(),
    )
    .unwrap();
    cleaned_up += 1;
    */

    println!("Cleaned up {cleaned_up} files.");
}

fn gen_alt() -> f32 {
    let mut rng = rand::thread_rng();
    return Uniform::new(MIN_ALT as u32, (MAX_ALT + 1.) as u32).sample(&mut rng) as f32;
}

fn gen_pos(alt: f32) -> Vec2 {
    let mut rng = rand::thread_rng();
    let frame_width = 2. * (FOV_DEG / 2.).to_radians().tan() * alt;
    let max = frame_width / 2. - PAD_SIZE / 2.;

    let x = Uniform::new(-max as i32, (max + 1.) as i32).sample(&mut rng) as f32;
    let y = Uniform::new(-max as i32, (max + 1.) as i32).sample(&mut rng) as f32;

    return Vec2::new(x, y);
}

fn gen_pos_pbf(alt: f32) -> Vec2 {
    const CENTER_SIZE: f32 = 0.2;

    let mut rng = rand::thread_rng();
    let frame_width = 2. * (FOV_DEG / 2.).to_radians().tan() * alt;
    let max = frame_width / 2. - CENTER_SIZE / 2.;

    let x = Uniform::new(-max, max).sample(&mut rng) as f32;
    let y = Uniform::new(-max, max).sample(&mut rng) as f32;

    return Vec2::new(x, y);
}

fn gen_sway() -> Quat {
    let mut rng = rand::thread_rng();
    let max = MAX_CAM_SWAY_DEG;
    let max_roll = MAX_CAM_SWAY_DEG_ROLL;

    let x = (Uniform::new(-max as i32, (max + 1.) as i32).sample(&mut rng) as f32).to_radians();
    let y = (Uniform::new(-max as i32, (max + 1.) as i32).sample(&mut rng) as f32).to_radians();
    let z = (Uniform::new(-max_roll as i32, (max_roll + 1.) as i32).sample(&mut rng) as f32)
        .to_radians();

    return Quat::from_euler(EulerRot::YXZ, y, x, z);
}

pub fn update_mesh_uvs_for_number_of_tiles(mesh: &mut Mesh, number_of_tiles: (f32, f32)) {
    if let Some(VertexAttributeValues::Float32x2(uvs)) = mesh.attribute_mut(Mesh::ATTRIBUTE_UV_0) {
        for uv in uvs {
            uv[0] *= number_of_tiles.0;
            uv[1] *= number_of_tiles.1;
        }
    }
}

fn setup(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut images: ResMut<Assets<Image>>,
    asset_server: Res<AssetServer>,
    mut export_sources: ResMut<Assets<ImageExportSource>>,
) {
    // Create an image output texture.
    let output_texture_handle = {
        let size = Extent3d {
            width: 416,
            height: 416,
            ..default()
        };
        let mut export_texture = Image {
            texture_descriptor: TextureDescriptor {
                label: None,
                size,
                dimension: TextureDimension::D2,
                format: TextureFormat::Rgba8UnormSrgb,
                mip_level_count: 1,
                sample_count: 1,
                usage: TextureUsages::COPY_DST
                    | TextureUsages::COPY_SRC
                    | TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            },
            ..default()
        };
        export_texture.resize(size);

        images.add(export_texture)
    };

    // Initiate camera
    let camera_transform = Transform::from_xyz(0., 0., 0.).looking_at(Vec3::ZERO, Vec3::Y);
    commands.spawn((
        Camera3dBundle {
            projection: Projection::Perspective(PerspectiveProjection {
                fov: FOV_DEG.to_radians(),
                ..Default::default()
            }),
            transform: camera_transform,
            camera: CameraDetails {
                target: RenderTarget::Image(output_texture_handle.clone()),
                ..Default::default()
            },
            ..Default::default()
        },
        Camera,
    ));
    commands.spawn((
        Camera3dBundle {
            projection: Projection::Perspective(PerspectiveProjection {
                fov: FOV_DEG.to_radians(),
                ..Default::default()
            }),
            transform: camera_transform,
            ..Default::default()
        },
        Camera,
    ));

    // Spawn the ImageExportBundle to initiate the export of the output into images
    commands.spawn(ImageExportBundle {
        source: export_sources.add(output_texture_handle.into()),
        settings: ImageExportSettings {
            // Where frames will be sent to
            output_dir: "out/images/".into(),
            // Choose "exr" for HDR renders.
            extension: "png".into(),
        },
    });

    let to_load = [
        "bottle_dropoff.png",
        "medkit_dropoff.png",
        "smores_dropoff.png",
        "bottle_pickup.png",
        "medkit_pickup.png",
        "smores_pickup.png",
    ];

    let mut loaded: Vec<Handle<Image>> = Vec::new();
    for i in to_load {
        let texture = asset_server.load(i);
        /*
        loaded.push(materials.add(StandardMaterial {
            base_color_texture: Some(texture),
            alpha_mode: AlphaMode::Blend,
            unlit: true,
            ..Default::default()
        }));
        */
        loaded.push(texture);
    }

    let mut ground_mesh = Mesh::from(shape::Quad::new(Vec2::new(10000., 10000.)));
    update_mesh_uvs_for_number_of_tiles(&mut ground_mesh, (100., 100.));

    let mut ground = Vec::new();

    for texture in asset_server.load_folder("ground").unwrap() {
        let texture: Handle<Image> = texture.typed();
        /*
        ground.push(materials.add(StandardMaterial {
            base_color_texture: Some(texture),
            alpha_mode: AlphaMode::Blend,
            unlit: true,
            ..Default::default()
        }));
        */
        ground.push(texture);
    }

    commands.insert_resource(Textures {
        ground,
        bottle_dropoff: loaded[0].clone(),
        medkit_dropoff: loaded[1].clone(),
        smores_dropoff: loaded[2].clone(),
        bottle_pickup: loaded[3].clone(),
        medkit_pickup: loaded[4].clone(),
        smores_pickup: loaded[5].clone(),
        pad_mesh: meshes.add(Mesh::from(shape::Quad::new(Vec2::new(PAD_SIZE, PAD_SIZE)))),
        ground_mesh: meshes.add(ground_mesh),
    });
}

fn simulate_frame(
    mut commands: Commands,
    mut cam_query: Query<(&Camera, &mut Transform, &CameraDetails)>,
    mut counter: ResMut<Counter>,
    mut exit: EventWriter<AppExit>,
    pad_query: Query<(Entity, &Pad)>,
    ground_query: Query<(Entity, &Ground)>,
    textures: Res<Textures>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let mut rng = rand::thread_rng();

    // Reset the camera
    let mut alt = gen_alt();
    let mut sway = gen_sway();
    let mut is_pbf = false;

    let frame_id = Uniform::new(0, 8).sample(&mut rng);
    // This frame is a close-up frame
    if frame_id == 0 {
        let max_roll = MAX_CAM_SWAY_DEG_ROLL;
        let z = (Uniform::new(-max_roll as i32, (max_roll + 1.) as i32).sample(&mut rng) as f32)
            .to_radians();
        sway = Quat::from_euler(EulerRot::YXZ, 0.0, 0.0, z);
        alt = Uniform::new(3.0, MIN_ALT).sample(&mut rng);
    // This frame is pbf
    } else if frame_id == 1 {
        is_pbf = true;

        let max_roll = MAX_CAM_SWAY_DEG_ROLL;
        let z = (Uniform::new(-max_roll as i32, (max_roll + 1.) as i32).sample(&mut rng) as f32)
            .to_radians();
        sway = Quat::from_euler(EulerRot::YXZ, 0.0, 0.0, z);

        alt = Uniform::new(1.0, 3.0).sample(&mut rng);
    }

    let mut curr_camera_transform = None;
    for (_, mut transform, _) in cam_query.iter_mut() {
        *transform = Transform::from_xyz(0., 0., alt);
        transform.look_at(Vec3::ZERO, Vec3::Y);
        transform.rotate(sway);
        curr_camera_transform = Some(transform.clone());
    }

    // Remove all pads
    for (entity, _) in pad_query.iter() {
        commands.entity(entity).despawn();
    }

    // Remove all ground
    for (entity, _) in ground_query.iter() {
        commands.entity(entity).despawn();
    }

    /* // Add some color offsets to every single material
    for (_, mat) in materials.iter_mut() {
        mat.base_color = Color::hsl(0., 0., Uniform::new(0.5, 1.0).sample(&mut rng));
    }
    */

    // Add a ground
    let ground_num = Uniform::new(0, textures.ground.len()).sample(&mut rng);
    let ground_offset_max: f32 = 1000.0;
    commands.spawn((
        PbrBundle {
            mesh: textures.ground_mesh.clone(),
            material: materials.add(StandardMaterial {
                base_color_texture: Some(textures.ground[ground_num].clone()),
                base_color: Color::hsl(0., 0., Uniform::new(0.5, 1.0).sample(&mut rng)),
                alpha_mode: AlphaMode::Blend,
                unlit: true,
                ..Default::default()
            }),
            transform: Transform::from_xyz(
                Uniform::new(0.0, ground_offset_max).sample(&mut rng),
                Uniform::new(0.0, ground_offset_max).sample(&mut rng),
                -10.,
            ),
            ..Default::default()
        },
        Ground,
    ));

    // Add a pad
    let pos = if is_pbf {
        gen_pos_pbf(alt)
    } else {
        gen_pos(alt)
    };
    let pad_num = Uniform::new(0, 6).sample(&mut rng);

    commands.spawn((
        PbrBundle {
            mesh: textures.pad_mesh.clone(),
            material: materials.add(StandardMaterial {
                base_color_texture: Some(match pad_num {
                    0 => textures.bottle_dropoff.clone(),
                    1 => textures.bottle_pickup.clone(),
                    2 => textures.medkit_dropoff.clone(),
                    3 => textures.medkit_pickup.clone(),
                    4 => textures.smores_dropoff.clone(),
                    5 => textures.smores_pickup.clone(),
                    _ => unreachable!(),
                }),
                base_color: Color::hsl(0., 0., Uniform::new(0.5, 1.0).sample(&mut rng)),
                alpha_mode: AlphaMode::Blend,
                unlit: true,
                ..Default::default()
            }),
            transform: Transform::from_xyz(pos.x, pos.y, 0.),
            ..Default::default()
        },
        Pad,
    ));

    // I dont know how or why, but doing this prevents bevy from not loading the
    // texture here and there.
    commands.spawn((
        PbrBundle {
            mesh: textures.pad_mesh.clone(),
            transform: Transform::from_xyz(pos.x, pos.y, 0.),
            ..Default::default()
        },
        Pad,
    ));

    // Calculate the camera position
    let (_, _, cam) = cam_query.iter_mut().next().unwrap();

    // Calculate the center and corner viewport coordinates
    let center = cam.world_to_viewport(
        &GlobalTransform::from(curr_camera_transform.unwrap()),
        Vec3::new(pos.x, pos.y, 0.),
    );
    let vertices_wrapped = vec![
        cam.world_to_viewport(
            &GlobalTransform::from(curr_camera_transform.unwrap()),
            Vec3::new(pos.x - PAD_SIZE / 2., pos.y + PAD_SIZE / 2., 0.),
        ),
        cam.world_to_viewport(
            &GlobalTransform::from(curr_camera_transform.unwrap()),
            Vec3::new(pos.x + PAD_SIZE / 2., pos.y - PAD_SIZE / 2., 0.),
        ),
        cam.world_to_viewport(
            &GlobalTransform::from(curr_camera_transform.unwrap()),
            Vec3::new(pos.x - PAD_SIZE / 2., pos.y - PAD_SIZE / 2., 0.),
        ),
        cam.world_to_viewport(
            &GlobalTransform::from(curr_camera_transform.unwrap()),
            Vec3::new(pos.x + PAD_SIZE / 2., pos.y + PAD_SIZE / 2., 0.),
        ),
    ];

    let mut vertices = vec![];
    let mut everything_exists = true;
    for v in vertices_wrapped {
        if v.is_none() {
            everything_exists = false;
            break;
        } else {
            vertices.push(v.unwrap());
        }
    }

    if everything_exists {
        let mut smallest_x = vertices[0].x;
        let mut biggest_x = vertices[0].x;
        let mut smallest_y = vertices[0].y;
        let mut biggest_y = vertices[0].y;

        for v in vertices {
            if v.x < smallest_x {
                smallest_x = v.x;
            } else {
                biggest_x = v.x
            }

            if v.y < smallest_y {
                smallest_y = v.y;
            } else {
                biggest_y = v.y
            }
        }

        println!("X range is gonna be: {smallest_x} - {biggest_x}");
        println!("Y range is gonna be: {smallest_y} - {biggest_y}");

        let mut center = center.unwrap() / 416.;
        let mut top_left = Vec2::new(smallest_x, biggest_y) / 416.;
        let mut bottom_right = Vec2::new(biggest_x, smallest_y) / 416.;

        // The origin should be at top left, not bottom left
        center.y = 1. - center.y;
        top_left.y = 1. - top_left.y;
        bottom_right.y = 1. - bottom_right.y;

        if is_pbf && (center.x < 1. && center.x > 0.) && (center.y < 1. && center.y > 0.) {
            std::fs::write(
                format!("out/labels/{:05}.txt", counter.current),
                format!("6 {} {} 0.1 0.1", center.x, center.y),
            )
            .unwrap();
        } else if (top_left.x < 1. && top_left.x > 0.)
            && (top_left.y < 1. && top_left.y > 0.)
            && (bottom_right.x < 1. && bottom_right.x > 0.)
            && (bottom_right.y < 1. && bottom_right.y > 0.)
        {
            let size_of_pad = (bottom_right - top_left).abs();

            // Now, despite the good calculations we did earlier to make a good
            // bounding box, one of the sizes in `size_of_pad` is correct, and another one
            // is too slim (for whatever reason). Therefor, take the bigger axes and set
            // the smaller one to the bigger one.
            // TODO: ^ This is not a good solution at all, but it fixes the damn slimming.
            let size: f32;
            if size_of_pad.x > size_of_pad.y {
                size = size_of_pad.x;
            } else {
                size = size_of_pad.y;
            }

            // If altitude is low enough, we can detect a pad center too
            if alt <= 15.0 {
                std::fs::write(
                    format!("out/labels/{:05}.txt", counter.current),
                    format!("{pad_num} {} {} {} {}\n", center.x, center.y, size, size)
                        + &format!("6 {} {} 0.1 0.1", center.x, center.y),
                )
                .unwrap();
            } else {
                std::fs::write(
                    format!("out/labels/{:05}.txt", counter.current),
                    format!("{pad_num} {} {} {} {}", center.x, center.y, size, size),
                )
                .unwrap();
            }
        } else {
            println!(
                "Not using scene {}, since pad may be out of bounds!",
                counter.current
            );
            // Since this one wont be used, gen another one later
            counter.max += 1;
        }
    }

    if counter.current > counter.max {
        exit.send(AppExit);
    }

    counter.current += 1;
    std::thread::sleep(std::time::Duration::from_millis(500));
}

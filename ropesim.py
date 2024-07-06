from dataclasses import dataclass
from tqdm import tqdm
from typing import Optional
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame as pg
from pathlib import Path

@dataclass
class Settings:
    duration_seconds: float
    timestep: float


@dataclass
class Mass:
    # Can move, can have ropes attached, has speed/ momentum ect.
    name: str

    # position
    x: float  # m, represents horizontal
    y: float  # m
    # velocity
    vx: float  # m/s, represents horizontal
    vy: float  # m/s
    # mass
    mass: float  # kg
    # force
    fx: float  # N, represents horizontal
    fy: float  # N

    def snapshot(self):
        return (self.name, self.x, self.y)


@dataclass
class Anchor:
    # Can't move, can have ropes attached
    name: str

    # position
    x: float  # m, represents horizontal
    y: float  # m


@dataclass
class Rope:
    # Ropes act as springs which only apply force when in tension.
    # They are massless, and only apply force along the direction of the rope.
    # They have a length, and exert no force when the rope length is less than that length.
    # f/length

    start: Mass | Anchor
    end: Mass | Anchor

    length: float  # m
    spring: float  # N to stretch 100%

    tension: Optional[float] = None  # N

    def calculate_tension(self, distance):
        if distance <= self.length:
            self.tension = 0
        else:
            self.tension = self.spring * (distance - self.length)

    def calculate_forces(self):
        # force on start
        # note: the force on end is the negative of force on start
        x_dist = self.start.x - self.end.x
        y_dist = self.start.y - self.end.y
        distance = (x_dist**2 + y_dist**2) ** 0.5
        if distance == 0:
            return 0, 0

        self.calculate_tension(distance)

        # Negative because this is a 'pull' not a 'push'
        fx = -x_dist / distance * self.tension
        fy = -y_dist / distance * self.tension
        return fx, fy

    def snapshot(self):
        return (self.start.x, self.start.y, self.end.x, self.end.y, self.tension)


def force_at_100_percent_stretch():
    # Calculation of spring constant
    stretch = 0.05  # 5% stretch
    force_at_stretch = 1500  # N
    return force_at_stretch / stretch


def fall_during_tyrolean():
    masses = [
        Mass(name="person", x=10.0, y=8.0, vx=0.0, vy=0.0, fx=0.0, fy=0.0, mass=80.0),
    ]
    anchors = [
        Anchor(x=5.0, y=8.5, name="belay"),
        Anchor(x=15.0, y=8.0, name="belay"),
    ]

    ropes = [
        Rope(
            start=masses[0],
            end=anchors[0],
            length=5.5,
            spring=force_at_100_percent_stretch(),
        ),
        Rope(
            start=masses[0],
            end=anchors[1],
            length=5.5,
            spring=force_at_100_percent_stretch(),
        ),
    ]
    return masses, anchors, ropes


def fall_from_anchor():
    masses = [
        Mass(name="person", x=10.0, y=8.0, vx=0.0, vy=0.0, fx=0.0, fy=0.0, mass=80.0),
    ]
    anchors = [Anchor(x=10.0, y=8.0, name="belay")]
    ropes = [
        Rope(
            start=masses[0],
            end=anchors[0],
            length=6,
            spring=force_at_100_percent_stretch(),
        ),
    ]
    return masses, anchors, ropes


def simulate(settings, masses, anchors, ropes) -> list:
    GRAVITY = 9.8

    # TODO figure out appropriate damping
    DAMPING_CONSTANT = 2000000
    DAMPING_ENABLED = False

    snapshots = []
    for i in tqdm(range(1, int(settings.duration_seconds / settings.timestep) + 1)):
        current_time = i * settings.timestep
        # Reset forces
        for mass in masses:
            mass.fx = 0.0
            mass.fy = -GRAVITY * mass.mass

        # Apply force from ropes
        for rope in ropes:
            fx, fy = rope.calculate_forces()

            if fx > 0 or fy > 0:
                if isinstance(rope.start, Mass):
                    rope.start.fx += fx
                    rope.start.fy += fy
                    if DAMPING_ENABLED:
                        rope.start.fx -= (
                            DAMPING_CONSTANT * rope.start.vx / rope.start.mass
                        ) * settings.timestep
                        rope.start.fy -= (
                            DAMPING_CONSTANT * rope.start.vy / rope.start.mass
                        ) * settings.timestep

                if isinstance(rope.end, Mass):
                    rope.end.fx -= fx
                    rope.end.fy -= fy
                    if DAMPING_ENABLED:
                        rope.end.fx -= (
                            DAMPING_CONSTANT * rope.end.vx / rope.end.mass
                        ) * settings.timestep
                        rope.end.fy -= (
                            DAMPING_CONSTANT * rope.end.vy / rope.end.mass
                        ) * settings.timestep

        # Apply accelerations to adjust velocities
        for mass in masses:
            mass.vx += (mass.fx / mass.mass) * settings.timestep
            mass.vy += (mass.fy / mass.mass) * settings.timestep

        # Update positions
        for mass in masses:
            mass.x += settings.timestep * mass.vx
            mass.y += settings.timestep * mass.vy

        # Save a snapshot for rendering later
        snapshots.append(
            [
                [mass.snapshot() for mass in masses],
                [rope.snapshot() for rope in ropes],
            ]
        )

    return snapshots


def render(simulation_settings, masses, anchors, ropes, snapshots, save=False):
    FPS = 60
    SIMULATION_SPEED = 1

    # Load pygame fullscreen
    pg.init()
    clock = pg.time.Clock()
    screen = pg.display.set_mode((1920, 1080), pg.SCALED, vsync=1)
    info = pg.display.Info()
    width, height = info.current_w, info.current_h

    # Setup viewbox from 0-10 x and don't distort the y axis
    max_x = 20
    max_y = height / width * max_x

    def draw_circle(surface, x, y, radius, colour, outline=None):
        center = (width * x / max_x, height * (1 - y / max_y))
        if outline:
            pg.draw.circle(surface, (0, 0, 0), center, radius + outline)
        pg.draw.circle(surface, colour, center, radius)

    def draw_line(surface, x1, y1, x2, y2, colour, thickness=4):
        pg.draw.line(
            surface,
            colour,
            (width * x1 / max_x, height * (1 - y1 / max_y)),
            (width * x2 / max_x, height * (1 - y2 / max_y)),
            thickness,
        )

    def rope_colour_scale(tension):
        nothing = (0, 255, 0)
        start = (255, 255, 102)
        mid = (255, 153, 102)
        end = (128, 0, 0)

        if tension == 0 or tension is None:
            return nothing
        elif tension <= 5000:
            ratio = tension / 5000
            return tuple([(1 - ratio) * i + ratio * j for i, j in zip(start, mid)])
        elif tension <= 10000:
            ratio = (tension - 5000) / 5000
            return tuple([(1 - ratio) * i + ratio * j for i, j in zip(mid, end)])
        else:
            return end

    # Create a background
    background = pg.surface.Surface((width, height))
    background.fill((100, 100, 100))
    for anchor in anchors:
        draw_circle(background, anchor.x, anchor.y, 20, (200, 0, 0), outline=2)

    total_frame_count = int(
        simulation_settings.duration_seconds * FPS / SIMULATION_SPEED
    )
    for i in range(total_frame_count):
        # Handle quit
        for e in pg.event.get():
            if e.type == pg.QUIT:
                return
            elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                pg.quit()
                return

        snapshot_index = int(i / total_frame_count * len(snapshots))

        # Handle masses
        masses_surface = pg.surface.Surface((width, height), pg.SRCALPHA, 32)
        for name, x, y in snapshots[snapshot_index][0]:
            draw_circle(masses_surface, x, y, 20, (0, 100, 0), outline=2)

        # Handle ropes
        ropes_surface = pg.surface.Surface((width, height), pg.SRCALPHA, 32)
        for rope_index, snapshot_data in enumerate(snapshots[snapshot_index][1]):
            start_x, start_y, end_x, end_y, tension = snapshot_data
            rope = ropes[rope_index]
            colour = rope_colour_scale(tension)
            draw_line(masses_surface, start_x, start_y, end_x, end_y, colour)

        screen.blit(background, (0, 0))
        screen.blit(masses_surface, (0, 0))
        screen.blit(ropes_surface, (0, 0))
        clock.tick(FPS)
        pg.display.update()

        if save:
            pg.image.save(screen, Path(__file__).parent.joinpath("video-frames", f"frame-{i:0>4}.png"))
    pg.quit()

    if save:
        print("ffmpeg -f image2 -r 60 -pattern_type glob -i 'video-frames/*.png' -vcodec libx264 -crf 22 video.mp4")



def main():
    simulation_settings = Settings(
        duration_seconds=4,
        timestep=0.005,
    )
    masses, anchors, ropes = fall_during_tyrolean()
    # masses, anchors, ropes = fall_from_anchor()

    snapshots = simulate(simulation_settings, masses, anchors, ropes)

    render(simulation_settings, masses, anchors, ropes, snapshots, save=True)


# For later;
# Add a graph of the tension in certain parts which shows the value vs time

# When not in tension add a waviness (sine wave) which uses up the slack in the rope
    # 1. simple sine wave that always has 1 period and amplitude adjusts to use up the spare distance
    # 2. change from 1 period to 10 periods from 0 length to full length with an amplitude adjustment also
    # 3. add a limit to the amplitude adjustment

# Add a method to mark a "moment of interest" and render that part in slow motion.

# Auto detect appropriate bounds for video with a small margin

if __name__ == "__main__":
    main()

import math
import random

import pygame

from scripts.particle import Particle
from scripts.spark import Spark


class PhysicsEntity:
    def __init__(self, game, e_type, pos, size):
        self.game = game
        self.type = e_type
        self.pos = list(pos)
        self.size = size
        self.velocity = [0, 0]
        self.collisions = {"up": False, "down": False, "right": False, "left": False}

        self.action = ""
        self.anim_offset = (-3, -3)
        self.flip = False
        self.set_action("idle")

        self.last_movement = [0, 0]

    def rect(self):
        return pygame.Rect(self.pos[0], self.pos[1], self.size[0], self.size[1])

    def set_action(self, action):
        if action != self.action:
            self.action = action
            self.animation = self.game.assets[self.type + "/" + self.action].copy()

    def update(self, tilemap, movement=(0, 0)):
        self.collisions = {"up": False, "down": False, "right": False, "left": False}

        frame_movement = (
            movement[0] + self.velocity[0],
            movement[1] + self.velocity[1],
        )

        self.pos[0] += frame_movement[0]
        entity_rect = self.rect()
        if tilemap:
            for rect in tilemap.physics_rects_around(self.pos):
                if entity_rect.colliderect(rect):
                    if frame_movement[0] > 0:
                        entity_rect.right = rect.left
                        self.collisions["right"] = True
                    if frame_movement[0] < 0:
                        entity_rect.left = rect.right
                        self.collisions["left"] = True
                    self.pos[0] = entity_rect.x

        self.pos[1] += frame_movement[1]
        entity_rect = self.rect()
        if tilemap:
            for rect in tilemap.physics_rects_around(self.pos):
                if entity_rect.colliderect(rect):
                    if frame_movement[1] > 0:
                        entity_rect.bottom = rect.top
                        self.collisions["down"] = True
                    if frame_movement[1] < 0:
                        entity_rect.top = rect.bottom
                        self.collisions["up"] = True
                    self.pos[1] = entity_rect.y

        if movement[0] > 0:
            self.flip = False
        if movement[0] < 0:
            self.flip = True

        self.last_movement = movement

        self.velocity[1] = min(5, self.velocity[1] + 0.1)

        if self.collisions["down"] or self.collisions["up"]:
            self.velocity[1] = 0

        self.animation.update()

    def render(self, surf, offset=(0, 0)):
        surf.blit(
            pygame.transform.flip(self.animation.img(), self.flip, False),
            (
                self.pos[0] - offset[0] + self.anim_offset[0],
                self.pos[1] - offset[1] + self.anim_offset[1],
            ),
        )


class Blob(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, "tblob", pos, size)
        self.health = 3
        self.speed = 0.5  # Base movement speed

        # State Management
        self.state = "idle"
        self.aggro_distance = 150  # The radius (in pixels) to start chasing the player

        # Idle State Properties (for wandering)
        self.idle_timer = 0
        self.idle_movement = [0, 0]

        # Chase State Properties (for wavy movement)
        self.chase_timer = 0  # This will be the input for our sine wave

        self.set_action("idle")

    def update(self, player, tilemap, movement=(0, 0)):
        # --- 1. Calculate distance to the player to decide the state ---
        dx = player.pos[0] - self.pos[0]
        dy = player.pos[1] - self.pos[1]
        distance = math.sqrt(dx**2 + dy**2)

        # --- 2. State Transition Logic ---
        if distance < self.aggro_distance:
            self.state = "chase"
        else:
            self.state = "idle"

        # --- 3. Execute Behavior Based on State ---
        vel = (0, 0)  # Final velocity for this frame

        if self.state == "chase":
            # --- CHASE BEHAVIOR (Wavy Movement) ---

            # a. Calculate the direct angle to the player
            angle_to_player = math.atan2(dy, dx)

            # b. Calculate the perpendicular angle for the wave motion
            # Adding/subtracting pi/2 (90 degrees) gives a perpendicular vector
            perp_angle = angle_to_player + math.pi / 2

            # c. Use a sine wave to create an offset
            # The 'chase_timer' increases over time, creating the wave effect.
            # The 'amplitude' controls how wide the wave is.
            wave_frequency = 0.1
            wave_amplitude = 0.6
            offset = math.sin(self.chase_timer * wave_frequency) * wave_amplitude

            # d. Combine the direct movement with the wavy offset
            # The enemy moves mainly towards the player but also shifts along the perpendicular axis
            vel_x = (
                math.cos(angle_to_player) * self.speed + math.cos(perp_angle) * offset
            )
            vel_y = (
                math.sin(angle_to_player) * self.speed + math.sin(perp_angle) * offset
            )

            vel = (vel_x, vel_y)

            # Increment the timer for the sine wave
            self.chase_timer += 1

        elif self.state == "idle":
            # --- IDLE BEHAVIOR (Wandering) ---

            # a. Countdown the timer. If it's running, keep moving.
            self.idle_timer -= 1

            # b. When the timer runs out, pick a new direction and reset the timer
            if self.idle_timer <= 0:
                # Reset timer to a random duration (e.g., 1 to 2 seconds at 60 FPS)
                self.idle_timer = random.randint(60, 120)

                # Pick a new random angle to move in
                random_angle = random.uniform(0, 2 * math.pi)

                # Set a new movement vector (slower than chase speed)
                idle_speed = self.speed * 0.5
                self.idle_movement = (
                    math.cos(random_angle) * idle_speed,
                    math.sin(random_angle) * idle_speed,
                )

            vel = self.idle_movement

        # --- 4. Call the parent update method with the calculated velocity ---
        super().update(tilemap, movement=vel)


class Enemy(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, "enemy", pos, size)

        self.walking = 0

    def update(self, tilemap, movement=(0, 0)):
        if self.walking:
            if tilemap.solid_check(
                (self.rect().centerx + (-7 if self.flip else 7), self.pos[1] + 23)
            ):
                if self.collisions["right"] or self.collisions["left"]:
                    self.flip = not self.flip
                else:
                    movement = (movement[0] - 0.5 if self.flip else 0.5, movement[1])
            else:
                self.flip = not self.flip
            self.walking = max(0, self.walking - 1)
            if not self.walking:
                dis = (
                    self.game.player.pos[0] - self.pos[0],
                    self.game.player.pos[1] - self.pos[1],
                )
                if abs(dis[1]) < 16:
                    if self.flip and dis[0] < 0:
                        self.game.sfx["shoot"].play()
                        self.game.projectiles.append(
                            [[self.rect().centerx - 7, self.rect().centery], -1.5, 0]
                        )
                        for i in range(4):
                            self.game.sparks.append(
                                Spark(
                                    self.game.projectiles[-1][0],
                                    random.random() - 0.5 + math.pi,
                                    2 + random.random(),
                                )
                            )
                    if not self.flip and dis[0] > 0:
                        self.game.sfx["shoot"].play()
                        self.game.projectiles.append(
                            [[self.rect().centerx + 7, self.rect().centery], 1.5, 0]
                        )
                        for i in range(4):
                            self.game.sparks.append(
                                Spark(
                                    self.game.projectiles[-1][0],
                                    random.random() - 0.5,
                                    2 + random.random(),
                                )
                            )
        elif random.random() < 0.01:
            self.walking = random.randint(30, 120)

        super().update(tilemap, movement=movement)

        if movement[0] != 0:
            self.set_action("walk")
        else:
            self.set_action("idle")

        if abs(self.game.player.dashing) >= 50:
            if self.rect().colliderect(self.game.player.rect()):
                self.game.screenshake = max(16, self.game.screenshake)
                self.game.sfx["hit"].play()
                for i in range(30):
                    angle = random.random() * math.pi * 2
                    speed = random.random() * 5
                    self.game.sparks.append(
                        Spark(self.rect().center, angle, 2 + random.random())
                    )
                    self.game.particles.append(
                        Particle(
                            self.game,
                            "particle",
                            self.rect().center,
                            velocity=[
                                math.cos(angle + math.pi) * speed * 0.5,
                                math.sin(angle + math.pi) * speed * 0.5,
                            ],
                            frame=random.randint(0, 7),
                        )
                    )
                self.game.sparks.append(
                    Spark(self.rect().center, 0, 5 + random.random())
                )
                self.game.sparks.append(
                    Spark(self.rect().center, math.pi, 5 + random.random())
                )
                return True

    def render(self, surf, offset=(0, 0)):
        super().render(surf, offset=offset)

        if self.flip:
            surf.blit(
                pygame.transform.flip(self.game.assets["gun"], True, False),
                (
                    self.rect().centerx
                    - 4
                    - self.game.assets["gun"].get_width()
                    - offset[0],
                    self.rect().centery - offset[1],
                ),
            )
        else:
            surf.blit(
                self.game.assets["gun"],
                (self.rect().centerx + 4 - offset[0], self.rect().centery - offset[1]),
            )


class Player(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, "player", pos, size)
        self.air_time = 0
        self.jumps = 1
        self.wall_slide = False
        self.dashing = 0
        self.maxhealth = 250
        self.health = 250

    def update(self, tilemap, movement=(0, 0)):
        super().update(tilemap, movement=movement)

        self.air_time += 1

        if self.air_time > 120:
            if not self.game.dead:
                self.game.screenshake = max(16, self.game.screenshake)
            self.game.dead += 1

        if self.collisions["down"]:
            self.air_time = 0
            self.jumps = 1

        # self.wall_slide = False
        # if (self.collisions["right"] or self.collisions["left"]) and self.air_time > 4:
        #     self.wall_slide = True
        #     self.velocity[1] = min(self.velocity[1], 0.5)
        #     if self.collisions["right"]:
        #         self.flip = False
        #     else:
        #         self.flip = True
        #     self.set_action("wall_slide")

        if not self.wall_slide:
            if self.air_time > 4:
                self.set_action("jump")
            elif movement[0] != 0:
                self.set_action("walk")
            else:
                self.set_action("idle")

        if abs(self.dashing) in {60, 50}:
            for i in range(20):
                angle = random.random() * math.pi * 2
                speed = random.random() * 0.5 + 0.5
                pvelocity = [math.cos(angle) * speed, math.sin(angle) * speed]
                self.game.particles.append(
                    Particle(
                        self.game,
                        "particle",
                        self.rect().center,
                        velocity=pvelocity,
                        frame=random.randint(0, 7),
                    )
                )
        if self.dashing > 0:
            self.dashing = max(0, self.dashing - 1)
        if self.dashing < 0:
            self.dashing = min(0, self.dashing + 1)
        if abs(self.dashing) > 50:
            self.velocity[0] = abs(self.dashing) / self.dashing * 8
            if abs(self.dashing) == 51:
                self.velocity[0] *= 0.1
            pvelocity = [abs(self.dashing) / self.dashing * random.random() * 3, 0]
            self.game.particles.append(
                Particle(
                    self.game,
                    "particle",
                    self.rect().center,
                    velocity=pvelocity,
                    frame=random.randint(0, 7),
                )
            )

        if self.velocity[0] > 0:
            self.velocity[0] = max(self.velocity[0] - 0.1, 0)
        else:
            self.velocity[0] = min(self.velocity[0] + 0.1, 0)

    def render(self, surf, offset=(0, 0)):
        if abs(self.dashing) <= 50:
            super().render(surf, offset=offset)

    def jump(self):
        if self.wall_slide:
            if self.flip and self.last_movement[0] < 0:
                self.velocity[0] = 3.5
                self.velocity[1] = -2.5
                self.air_time = 5
                self.jumps = max(0, self.jumps - 1)
                return True
            elif not self.flip and self.last_movement[0] > 0:
                self.velocity[0] = -3.5
                self.velocity[1] = -2.5
                self.air_time = 5
                self.jumps = max(0, self.jumps - 1)
                return True

        elif self.jumps:
            self.velocity[1] = -3
            self.jumps -= 1
            self.air_time = 5
            return True

    def dash(self):
        if not self.dashing:
            self.game.sfx["dash"].play()
            if self.flip:
                self.dashing = -60
            else:
                self.dashing = 60

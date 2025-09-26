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
        self.speed = 0.5

        self.state = "idle"
        self.aggro_distance = 150

        self.idle_timer = 0
        self.idle_movement = [0, 0]

        self.chase_timer = 0

        self.shoot_cooldown = 0
        self.shoot_delay = 6

        self.set_action("idle")

    def update(self, player, tilemap, movement=(0, 0)):
        dx = player.pos[0] - self.pos[0]
        dy = player.pos[1] - self.pos[1]
        distance = math.sqrt(dx**2 + dy**2)

        if distance < self.aggro_distance:
            self.state = "chase"
        else:
            self.state = "idle"

        vel = (0, 0)

        if self.state == "chase":
            if self.shoot_cooldown > 0:
                self.shoot_cooldown -= 1

            if self.shoot_cooldown > 0:
                angle_to_player = math.atan2(dy, dx)
                perp_angle = angle_to_player + math.pi / 2
                wave_frequency = 0.1
                wave_amplitude = 0.6
                offset = math.sin(self.chase_timer * wave_frequency) * wave_amplitude
                vel_x = (
                    math.cos(angle_to_player) * self.speed
                    + math.cos(perp_angle) * offset
                )
                vel_y = (
                    math.sin(angle_to_player) * self.speed
                    + math.sin(perp_angle) * offset
                )
                vel = (vel_x, vel_y)
                self.chase_timer += 1
            else:
                self.shoot_cooldown = self.shoot_delay
                vel = (0, 0)
                angle_to_player = math.atan2(dy, dx)
                projectile_speed = 2.5
                vel_x = math.cos(angle_to_player) * projectile_speed
                vel_y = math.sin(angle_to_player) * projectile_speed
                self.game.projectiles.append(
                    {
                        "pos": list(self.rect().center),
                        "vel": [vel_x, vel_y],
                        "owner": "enemy",
                    }
                )

        elif self.state == "idle":
            self.idle_timer -= 1
            if self.idle_timer <= 0:
                self.idle_timer = random.randint(60, 120)
                random_angle = random.uniform(0, 2 * math.pi)
                idle_speed = self.speed * 0.5
                self.idle_movement = (
                    math.cos(random_angle) * idle_speed,
                    math.sin(random_angle) * idle_speed,
                )
            vel = self.idle_movement

        super().update(tilemap, movement=vel)


class Enemy(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, "enemy", pos, size)
        self.health = 5
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
                    if (self.flip and dis[0] < 0) or (not self.flip and dis[0] > 0):
                        self.game.sfx["shoot"].play()
                        angle = math.atan2(dis[1], dis[0])
                        speed = 1.5
                        vel_x = math.cos(angle) * speed
                        vel_y = math.sin(angle) * speed

                        spawn_pos = [
                            self.rect().centerx + (-7 if self.flip else 7),
                            self.rect().centery,
                        ]
                        self.game.projectiles.append(
                            {"pos": spawn_pos, "vel": [vel_x, vel_y], "owner": "enemy"}
                        )

                        for i in range(4):
                            spark_angle = angle + random.random() * 0.5 - 0.25
                            self.game.sparks.append(
                                Spark(
                                    self.game.projectiles[-1]["pos"],
                                    spark_angle,
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
                self.health = 0  # Instant kill on dash
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
        self.shoot_cooldown = 0

    def update(self, tilemap, movement=(0, 0)):
        super().update(tilemap, movement=movement)

        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

        self.air_time += 1

        if self.air_time > 120:
            if not self.game.dead:
                self.game.screenshake = max(16, self.game.screenshake)
            self.game.dead += 1

        if self.collisions["down"]:
            self.air_time = 0
            self.jumps = 1

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

    def shoot(self, mouse_pos):
        if self.shoot_cooldown == 0:
            self.shoot_cooldown = 15  # Cooldown in frames

            # Use camera offset to get world coordinates of mouse
            world_mouse_pos = (
                mouse_pos[0] + self.game.camera_offset[0],
                mouse_pos[1] + self.game.camera_offset[1],
            )

            dx = world_mouse_pos[0] - self.rect().centerx
            dy = world_mouse_pos[1] - self.rect().centery
            angle = math.atan2(dy, dx)
            speed = 4.0

            vel_x = math.cos(angle) * speed
            vel_y = math.sin(angle) * speed

            self.game.projectiles.append(
                {
                    "pos": list(self.rect().center),
                    "vel": [vel_x, vel_y],
                    "owner": "player",
                }
            )

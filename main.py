import os
import sys
import math
import random

import pygame

from scripts.utils import load_image, load_images, Animation
from scripts.entities import PhysicsEntity, Player, Enemy, Blob
from scripts.tilemap import Tilemap
from scripts.clouds import Clouds
from scripts.particle import Particle
from scripts.spark import Spark


class Game:
    def __init__(self):
        pygame.init()
        pygame.font.init()

        pygame.display.set_caption("ninja game")
        self.screen = pygame.display.set_mode((640, 480))
        self.display = pygame.Surface((320, 240), pygame.SRCALPHA)
        self.display_2 = pygame.Surface((320, 240))

        self.clock = pygame.time.Clock()

        self.movement = [False, False]

        self.font = pygame.font.Font(None, 16)

        self.assets = {
            "decor": load_images("tiles/decor"),
            "spawners": load_images("tiles/spawners"),
            "grass": load_images("tiles/grass"),
            "large_decor": load_images("tiles/large_decor"),
            "stone": load_images("tiles/stone"),
            "player": load_image("entities/player.png"),
            "background": load_image("background.png"),
            "clouds": load_images("clouds"),
            "tblob/idle": Animation(load_images("entities/blob/idle"), img_dur=6),
            "enemy/idle": Animation(load_images("entities/enemy/idle"), img_dur=6),
            "enemy/walk": Animation(load_images("entities/enemy/walk"), img_dur=4),
            "player/idle": Animation(load_images("entities/player/idle"), img_dur=6),
            "player/walk": Animation(load_images("entities/player/walk"), img_dur=4),
            "player/jump": Animation(load_images("entities/player/jump")),
            "particle/leaf": Animation(
                load_images("particles/leaf"), img_dur=20, loop=False
            ),
            "particle/particle": Animation(
                load_images("particles/particle"), img_dur=6, loop=False
            ),
            "gun": load_image("gun.png"),
            "projectile": load_image("projectile.png"),
        }

        self.sfx = {
            "jump": pygame.mixer.Sound("data/sfx/jump.wav"),
            "dash": pygame.mixer.Sound("data/sfx/dash.wav"),
            "hit": pygame.mixer.Sound("data/sfx/hit.wav"),
            "shoot": pygame.mixer.Sound("data/sfx/shoot.wav"),
            "ambience": pygame.mixer.Sound("data/sfx/ambience.wav"),
        }

        self.sfx["ambience"].set_volume(0.2)
        self.sfx["shoot"].set_volume(0.4)
        self.sfx["hit"].set_volume(0.8)
        self.sfx["dash"].set_volume(0.3)
        self.sfx["jump"].set_volume(0.7)

        self.clouds = Clouds(self.assets["clouds"], count=16)

        self.player = Player(self, (50, 50), (8, 15))

        self.tilemap = Tilemap(self, tile_size=16)

        self.level = 0
        self.load_level(self.level)

        self.screenshake = 0

    def load_level(self, map_id):
        self.tilemap.load("data/maps/" + str(map_id) + ".json")

        self.leaf_spawners = []
        for tree in self.tilemap.extract([("large_decor", 2)], keep=True):
            self.leaf_spawners.append(
                pygame.Rect(4 + tree["pos"][0], 4 + tree["pos"][1], 23, 13)
            )

        self.enemies = []
        self.blobs = []
        for spawner in self.tilemap.extract(
            [("spawners", 0), ("spawners", 1), ("spawners", 2)]
        ):
            if spawner["variant"] == 0:
                self.player.pos = spawner["pos"]
                self.player.air_time = 0
            elif spawner["variant"] == 2:
                self.blobs.append(Blob(self, spawner["pos"], (8, 8)))
            else:
                self.enemies.append(Enemy(self, spawner["pos"], (8, 15)))

        self.projectiles = []
        self.particles = []
        self.sparks = []

        self.scroll = [0, 0]
        self.dead = 0
        self.transition = -30

        self.camera_offset = [0, 0]

    def run(self):
        pygame.mixer.music.load("data/music.wav")
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)

        self.sfx["ambience"].play(-1)

        while True:
            self.display.fill((0, 0, 0, 0))
            self.display_2.blit(self.assets["background"], (0, 0))

            self.screenshake = max(0, self.screenshake - 1)

            if self.dead:
                self.dead += 1
                if self.dead >= 10:
                    self.transition = min(30, self.transition + 1)
                if self.dead > 40:
                    self.load_level(self.level)

            self.scroll[0] += (
                self.player.rect().centerx
                - self.display.get_width() / 2
                - self.scroll[0]
            ) / 30
            self.scroll[1] += (
                self.player.rect().centery
                - self.display.get_height() / 2
                - self.scroll[1]
            ) / 30
            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))
            self.camera_offset = render_scroll

            for rect in self.leaf_spawners:
                if random.random() * 49999 < rect.width * rect.height:
                    pos = (
                        rect.x + random.random() * rect.width,
                        rect.y + random.random() * rect.height,
                    )
                    self.particles.append(
                        Particle(
                            self,
                            "leaf",
                            pos,
                            velocity=[-0.1, 0.3],
                            frame=random.randint(0, 20),
                        )
                    )

            self.clouds.update()
            self.clouds.render(self.display_2, offset=render_scroll)

            self.tilemap.render(self.display, offset=render_scroll)

            for blob in self.blobs.copy():
                blob.update(self.player, self.tilemap, (0, 0))
                blob.render(self.display, offset=render_scroll)
                if blob.health <= 0:
                    self.blobs.remove(blob)
                    self.sfx["hit"].play()
                    for i in range(10):
                        angle = random.random() * math.pi * 2
                        self.sparks.append(
                            Spark(blob.rect().center, angle, 1 + random.random())
                        )

            for enemy in self.enemies.copy():
                enemy.update(self.tilemap, (0, 0))
                enemy.render(self.display, offset=render_scroll)
                if enemy.health <= 0:
                    self.enemies.remove(enemy)
                    self.sfx["hit"].play()
                    for i in range(15):
                        angle = random.random() * math.pi * 2
                        self.sparks.append(
                            Spark(enemy.rect().center, angle, 2 + random.random())
                        )

            if not self.dead:
                self.player.update(
                    self.tilemap, (self.movement[1] - self.movement[0], 0)
                )
                self.player.render(self.display, offset=render_scroll)

            for projectile in self.projectiles.copy():
                projectile["pos"][0] += projectile["vel"][0]
                projectile["pos"][1] += projectile["vel"][1]
                projectile["timer"] = projectile.get("timer", 0) + 1

                img = self.assets["projectile"]
                self.display.blit(
                    img,
                    (
                        projectile["pos"][0] - img.get_width() / 2 - render_scroll[0],
                        projectile["pos"][1] - img.get_height() / 2 - render_scroll[1],
                    ),
                )

                if self.tilemap.solid_check(projectile["pos"]):
                    self.projectiles.remove(projectile)
                    for i in range(4):
                        self.sparks.append(
                            Spark(
                                projectile["pos"],
                                random.random() - 0.5 + math.pi,
                                2 + random.random(),
                            )
                        )
                elif projectile["timer"] > 360:
                    self.projectiles.remove(projectile)

                if projectile["owner"] == "player":
                    hit = False
                    for enemy in self.enemies.copy():
                        if enemy.rect().collidepoint(projectile["pos"]):
                            enemy.health -= 1
                            self.projectiles.remove(projectile)
                            hit = True
                            break
                    if not hit:
                        for blob in self.blobs.copy():
                            if blob.rect().collidepoint(projectile["pos"]):
                                blob.health -= 1
                                self.projectiles.remove(projectile)
                                break

                elif projectile["owner"] == "enemy":
                    if abs(self.player.dashing) < 50:
                        if self.player.rect().collidepoint(projectile["pos"]):
                            self.projectiles.remove(projectile)
                            self.dead += 1
                            self.sfx["hit"].play()
                            self.screenshake = max(16, self.screenshake)
                            for i in range(30):
                                angle = random.random() * math.pi * 2
                                speed = random.random() * 5
                                self.sparks.append(
                                    Spark(
                                        self.player.rect().center,
                                        angle,
                                        2 + random.random(),
                                    )
                                )

            for spark in self.sparks.copy():
                kill = spark.update()
                spark.render(self.display, offset=render_scroll)
                if kill:
                    self.sparks.remove(spark)

            display_mask = pygame.mask.from_surface(self.display)
            display_sillhouette = display_mask.to_surface(
                setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0)
            )
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_sillhouette, offset)

            for particle in self.particles.copy():
                kill = particle.update()
                particle.render(self.display, offset=render_scroll)
                if particle.type == "leaf":
                    particle.pos[0] += math.sin(particle.animation.frame * 0.035) * 0.3
                if kill:
                    self.particles.remove(particle)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        scaled_mouse_pos = (
                            event.pos[0]
                            * (self.display.get_width() / self.screen.get_width()),
                            event.pos[1]
                            * (self.display.get_height() / self.screen.get_height()),
                        )
                        self.player.shoot(scaled_mouse_pos)
                        self.sfx["shoot"].play()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_a:
                        self.movement[0] = True
                    if event.key == pygame.K_d:
                        self.movement[1] = True
                    if event.key == pygame.K_w:
                        if self.player.jump():
                            self.sfx["jump"].play()
                    if event.key == pygame.K_SPACE:
                        self.player.dash()
                    if event.key == pygame.K_r:
                        self.player.reload()
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_a:
                        self.movement[0] = False
                    if event.key == pygame.K_d:
                        self.movement[1] = False

            # UI Rendering
            health_bar_bg = pygame.Rect(5, 5, 100, 10)
            health_ratio = self.player.health / self.player.maxhealth
            current_health_width = int(100 * health_ratio)
            current_health_bar = pygame.Rect(5, 5, current_health_width, 10)
            pygame.draw.rect(self.display_2, (255, 0, 0), health_bar_bg)
            if current_health_width > 0:
                pygame.draw.rect(self.display_2, (0, 255, 0), current_health_bar)

            ammo_text = self.font.render(
                f"AMMO: {self.player.ammo}/{self.player.max_ammo}",
                True,
                (255, 255, 255),
            )
            self.display_2.blit(ammo_text, (5, 20))

            if self.player.ammo == 0:
                reload_text = self.font.render(
                    "PRESS R TO RELOAD (-20 HP)", True, (255, 220, 220)
                )
                self.display_2.blit(
                    reload_text,
                    (
                        self.display_2.get_width() // 2 - reload_text.get_width() // 2,
                        self.display_2.get_height() - 20,
                    ),
                )

            self.display_2.blit(self.display, (0, 0))

            screenshake_offset = (
                random.random() * self.screenshake - self.screenshake / 2,
                random.random() * self.screenshake - self.screenshake / 2,
            )
            self.screen.blit(
                pygame.transform.scale(self.display_2, self.screen.get_size()),
                screenshake_offset,
            )
            pygame.display.update()
            self.clock.tick(60)


Game().run()

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
        self.ui_font = pygame.font.Font(None, 24)

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
        self.num_levels = len(
            [f for f in os.listdir("data/maps") if f.endswith(".json")]
        )
        self.load_level(self.level)

        self.screenshake = 0

        self.start_time = pygame.time.get_ticks()
        self.game_completed = False
        self.completion_time = 0

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
                self.player_spawn_pos = spawner["pos"]
                self.player.pos = list(self.player_spawn_pos)
                self.player.air_time = 0
                self.player.health = self.player.maxhealth
                self.player.ammo = self.player.max_ammo
                self.player.dash_duration = 60
            elif spawner["variant"] == 2:
                self.blobs.append(Blob(self, spawner["pos"], (65, 65)))
            else:
                self.enemies.append(Enemy(self, spawner["pos"], (8, 15)))

        self.projectiles = []
        self.particles = []
        self.sparks = []
        self.float_particles = []

        self.scroll = [0, 0]
        self.dead = 0
        self.death_type = None

        self.camera_offset = [0, 0]

        if map_id == 0:
            self.start_time = pygame.time.get_ticks()
            self.game_completed = False

    def respawn(self):
        self.player.health = max(0, self.player.health - 20)
        self.player.dash_duration = max(20, self.player.dash_duration - 10)
        self.player.pos = list(self.player_spawn_pos)
        self.player.air_time = 0
        self.player.velocity = [0, 0]
        self.dead = 0
        self.death_type = None

    def run(self):
        pygame.mixer.music.load("data/music.wav")
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)

        self.sfx["ambience"].play(-1)

        while True:
            self.display.fill((0, 0, 0, 0))
            self.display_2.blit(self.assets["background"], (0, 0))

            self.screenshake = max(0, self.screenshake - 1)

            if not len(self.enemies) and not self.dead:
                if self.level == self.num_levels - 1:
                    if not self.game_completed:
                        self.game_completed = True
                        self.completion_time = pygame.time.get_ticks() - self.start_time
                else:
                    self.level = min(self.level + 1, self.num_levels - 1)
                    self.load_level(self.level)
                    self.player.health = min(
                        self.player.maxhealth, self.player.health + 20
                    )

            if self.dead:
                self.dead += 1
                if self.dead > 40:
                    if self.death_type == "fall":
                        self.respawn()
                    elif self.death_type == "health":
                        self.level = 0
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

                if self.player.pos[1] > 500:
                    self.dead = 1
                    self.death_type = "fall"
                    self.sfx["hit"].play()
                    self.screenshake = max(16, self.screenshake)
                elif self.player.health <= 0:
                    self.dead = 1
                    self.death_type = "health"
                    self.sfx["hit"].play()
                    self.screenshake = max(16, self.screenshake)

            for projectile in self.projectiles.copy():
                projectile["pos"][0] += projectile["vel"][0]
                projectile["pos"][1] += projectile["vel"][1]
                projectile["timer"] = projectile.get("timer", 0) + 1

                img = self.assets["projectile"]

                render_pos_x = projectile["pos"][0] - render_scroll[0]
                render_pos_y = projectile["pos"][1] - render_scroll[1]

                if projectile["owner"] == "enemy":
                    glow_size = img.get_width() + 8
                    glow_surf = pygame.transform.scale(img, (glow_size, glow_size))
                    glow_surf.fill((255, 60, 60), special_flags=pygame.BLEND_RGB_MULT)
                    glow_surf.set_alpha(90)
                    self.display.blit(
                        glow_surf,
                        (
                            render_pos_x - glow_surf.get_width() / 2,
                            render_pos_y - glow_surf.get_height() / 2,
                        ),
                    )

                self.display.blit(
                    img,
                    (
                        render_pos_x - img.get_width() / 2,
                        render_pos_y - img.get_height() / 2,
                    ),
                )

                if self.tilemap.solid_check(projectile["pos"]):
                    if projectile in self.projectiles:
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
                    if projectile in self.projectiles:
                        self.projectiles.remove(projectile)

                if projectile["owner"] == "player":
                    hit = False
                    for enemy in self.enemies.copy():
                        if enemy.rect().collidepoint(projectile["pos"]):
                            enemy.health -= 1
                            enemy.hit_timer = 60
                            for i in range(4):
                                self.sparks.append(
                                    Spark(
                                        projectile["pos"],
                                        random.random() * math.pi * 2,
                                        1 + random.random(),
                                    )
                                )
                            if projectile in self.projectiles:
                                self.projectiles.remove(projectile)
                            hit = True
                            break
                    if not hit:
                        for blob in self.blobs.copy():
                            if blob.rect().collidepoint(projectile["pos"]):
                                blob.health -= 1
                                blob.hit_timer = 90
                                for i in range(4):
                                    self.sparks.append(
                                        Spark(
                                            projectile["pos"],
                                            random.random() * math.pi * 2,
                                            1 + random.random(),
                                        )
                                    )
                                if projectile in self.projectiles:
                                    self.projectiles.remove(projectile)
                                break

                elif projectile["owner"] == "enemy":
                    if (
                        not self.dead
                        and abs(self.player.dashing) < self.player.dash_duration - 10
                    ):
                        if self.player.rect().collidepoint(projectile["pos"]):
                            if projectile in self.projectiles:
                                self.projectiles.remove(projectile)
                            self.player.health = max(0, self.player.health - 20)
                            self.sfx["hit"].play()
                            self.screenshake = max(16, self.screenshake)

            for spark in self.sparks.copy():
                kill = spark.update()
                spark.render(self.display, offset=render_scroll)
                if kill:
                    self.sparks.remove(spark)

            for particle in self.float_particles.copy():
                particle["size"] -= 0.1
                particle["pos"][1] -= 0.2
                if particle["size"] <= 0:
                    self.float_particles.remove(particle)
                else:
                    pygame.draw.circle(
                        self.display,
                        particle["color"],
                        [
                            int(particle["pos"][0] - render_scroll[0]),
                            int(particle["pos"][1] - render_scroll[1]),
                        ],
                        int(particle["size"]),
                    )

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
                        if self.player.shoot(scaled_mouse_pos):
                            self.sfx["shoot"].play()
                    if event.button == 3:
                        self.player.reload()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_a:
                        self.movement[0] = True
                    if event.key == pygame.K_d:
                        self.movement[1] = True
                    if event.key == pygame.K_w:
                        if self.player.jump():
                            self.sfx["jump"].play()
                    if event.key == pygame.K_SPACE or event.key == pygame.K_s:
                        self.player.dash()
                    if event.key == pygame.K_r:
                        self.player.reload()
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_a:
                        self.movement[0] = False
                    if event.key == pygame.K_d:
                        self.movement[1] = False

            self.display_2.blit(self.display, (0, 0))

            screenshake_offset = (
                random.random() * self.screenshake - self.screenshake / 2,
                random.random() * self.screenshake - self.screenshake / 2,
            )
            self.screen.blit(
                pygame.transform.scale(self.display_2, self.screen.get_size()),
                screenshake_offset,
            )

            health_bar_bg = pygame.Rect(10, 10, 200, 18)
            health_ratio = self.player.health / self.player.maxhealth
            current_health_width = int(200 * health_ratio)
            current_health_bar = pygame.Rect(10, 10, current_health_width, 18)
            pygame.draw.rect(self.screen, (150, 0, 0), health_bar_bg)
            if current_health_width > 0:
                pygame.draw.rect(self.screen, (0, 255, 0), current_health_bar)

            ammo_text = self.ui_font.render(
                f"AMMO: {self.player.ammo}/{self.player.max_ammo}",
                True,
                (255, 255, 255),
            )
            self.screen.blit(ammo_text, (10, 35))

            health_text = self.ui_font.render(
                f"HP: {int(self.player.health)}/{self.player.maxhealth}",
                True,
                (255, 255, 255),
            )
            self.screen.blit(health_text, (220, 11))

            level_text = self.ui_font.render(
                f"Level: {self.level + 1} / {self.num_levels}", True, (255, 255, 255)
            )
            self.screen.blit(level_text, (10, 60))

            enemies_text = self.ui_font.render(
                f"Enemies Left: {len(self.enemies)}", True, (255, 255, 255)
            )
            enemies_text_rect = enemies_text.get_rect(
                topright=(self.screen.get_width() - 10, 10)
            )
            self.screen.blit(enemies_text, enemies_text_rect)

            if not self.game_completed:
                elapsed_time = pygame.time.get_ticks() - self.start_time
            else:
                elapsed_time = self.completion_time

            seconds = int(elapsed_time / 1000) % 60
            minutes = int(elapsed_time / 60000)
            timer_text = self.ui_font.render(
                f"Time: {minutes:02}:{seconds:02}", True, (255, 255, 255)
            )
            timer_rect = timer_text.get_rect(
                centerx=self.screen.get_width() // 2, top=10
            )
            self.screen.blit(timer_text, timer_rect)

            if self.player.ammo == 0:
                reload_text = self.ui_font.render(
                    "PRESS R TO RELOAD (-20 HP)", True, (255, 220, 220)
                )
                reload_text_rect = reload_text.get_rect(
                    center=(self.screen.get_width() // 2, self.screen.get_height() - 30)
                )
                self.screen.blit(reload_text, reload_text_rect)

            if self.game_completed:
                win_text = self.ui_font.render("YOU WIN!", True, (255, 255, 0))
                win_rect = win_text.get_rect(
                    center=(self.screen.get_width() // 2, self.screen.get_height() // 2)
                )
                self.screen.blit(win_text, win_rect)

            pygame.display.update()
            self.clock.tick(60)


Game().run()

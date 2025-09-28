import os
import sys
import math
import random
import asyncio  # Make sure this is imported
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

        pygame.display.set_caption("Tiny Hunter")
        self.screen = pygame.display.set_mode((640, 480))
        self.display = pygame.Surface((320, 240), pygame.SRCALPHA)
        self.display_2 = pygame.Surface((320, 240))

        self.clock = pygame.time.Clock()

        self.movement = [False, False]

        self.font = pygame.font.Font(None, 16)
        self.ui_font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 48)

        self.assets = {
            "decor": load_images("tiles/decor"),
            "spawners": load_images("tiles/spawners"),
            "grass": load_images("tiles/grass"),
            "large_decor": load_images("tiles/large_decor"),
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
            "howto": load_image("how to.png"),
        }

        # NOTE: For web, it's better to load sounds after an interaction.
        # But for simplicity, we'll keep it here. Convert all audio to .ogg or .mp3
        self.sfx = {
            "jump": pygame.mixer.Sound("data/sfx/jump.mp3"),
            "dash": pygame.mixer.Sound("data/sfx/dash.mp3"),
            "hit": pygame.mixer.Sound("data/sfx/hit.mp3"),
            "shoot": pygame.mixer.Sound("data/sfx/shoot.mp3"),
            "ambience": pygame.mixer.Sound("data/sfx/ambience.mp3"),
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
        try:
            self.num_levels = len(
                [f for f in os.listdir("data/maps") if f.endswith(".json")]
            )
        except FileNotFoundError:
            # Handle the case where the maps directory might not exist in the web build
            self.num_levels = 7  # Manually set the number of levels if needed

        self.load_level(self.level)

        self.screenshake = 0

        self.start_time = pygame.time.get_ticks()
        self.game_completed = False
        self.completion_time = 0

        self.show_start_screen = True
        self.enemies_defeated = 0
        self.blobs_defeated = 0

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
            self.enemies_defeated = 0
            self.blobs_defeated = 0

    def respawn(self):
        self.player.health = max(0, self.player.health - 20)
        self.player.dash_duration = max(20, self.player.dash_duration - 10)
        self.player.pos = list(self.player_spawn_pos)
        self.player.air_time = 0
        self.player.velocity = [0, 0]
        self.dead = 0
        self.death_type = None

    def render_text_with_outline(
        self, text, font, pos, text_color, outline_color=(0, 0, 0)
    ):
        text_surf = font.render(text, True, text_color)
        outline_surf = font.render(text, True, outline_color)

        for offset in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            self.screen.blit(outline_surf, (pos[0] + offset[0], pos[1] + offset[1]))

        self.screen.blit(text_surf, pos)

    # Renamed 'run' to 'main' and made it 'async'
    async def main(self):
        # The main 'while' loop. 'running' will be set to False to exit.
        running = True
        while running:
            # ================================================================= #
            # 1. EVENT HANDLING (Consolidated into one loop for all game states)
            # ================================================================= #
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False  # Instead of sys.exit()

                # Handle input for the START SCREEN or GAME COMPLETED screen
                if self.show_start_screen or self.game_completed:
                    if (
                        event.type == pygame.MOUSEBUTTONDOWN
                        or event.type == pygame.KEYDOWN
                    ):
                        # If we were on the win screen, reset the game
                        if self.game_completed:
                            self.game_completed = False
                            self.level = 0
                            self.load_level(self.level)

                        # Hide the start screen and start the music
                        if self.show_start_screen:
                            self.show_start_screen = False
                            pygame.mixer.music.load("data/music.mp3")
                            pygame.mixer.music.set_volume(0.5)
                            pygame.mixer.music.play(-1)
                            self.sfx["ambience"].play(-1)

                # Handle input for the MAIN GAME
                else:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            scaled_mouse_pos = (
                                event.pos[0]
                                * (self.display.get_width() / self.screen.get_width()),
                                event.pos[1]
                                * (
                                    self.display.get_height() / self.screen.get_height()
                                ),
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

            # ================================================================= #
            # 2. GAME STATE LOGIC & RENDERING (Using if/elif/else)
            # ================================================================= #

            # State 1: Game Completed Screen
            if self.game_completed:
                self.screen.fill((0, 0, 0))
                seconds = int(self.completion_time / 1000) % 60
                minutes = int(self.completion_time / 60000)
                time_str = f"Time: {minutes:02}:{seconds:02}"

                self.render_text_with_outline(
                    "YOU WIN!",
                    self.large_font,
                    (self.screen.get_width() // 2 - 120, 100),
                    (255, 255, 0),
                )
                self.render_text_with_outline(
                    time_str,
                    self.ui_font,
                    (self.screen.get_width() // 2 - 70, 200),
                    (255, 255, 255),
                )
                self.render_text_with_outline(
                    f"Enemies Defeated: {self.enemies_defeated}",
                    self.ui_font,
                    (self.screen.get_width() // 2 - 100, 240),
                    (255, 255, 255),
                )
                self.render_text_with_outline(
                    f"Blobs Defeated: {self.blobs_defeated}",
                    self.ui_font,
                    (self.screen.get_width() // 2 - 90, 270),
                    (255, 255, 255),
                )
                self.render_text_with_outline(
                    "Click or press any key to play again",
                    self.ui_font,
                    (self.screen.get_width() // 2 - 150, 400),
                    (200, 200, 200),
                )

            # State 2: Start Screen
            elif self.show_start_screen:
                # Scaled the 'howto' image in the __init__ to avoid doing it every frame
                try:
                    scaled_howto = pygame.transform.scale(
                        self.assets["howto"], self.screen.get_size()
                    )
                    self.screen.blit(scaled_howto, (0, 0))
                except:
                    self.screen.fill((0, 0, 0))
                    self.render_text_with_outline(
                        "Tiny Hunter",
                        self.large_font,
                        (self.screen.get_width() // 2 - 120, 100),
                        (255, 255, 255),
                    )
                    self.render_text_with_outline(
                        "Click or press any key to start",
                        self.ui_font,
                        (self.screen.get_width() // 2 - 150, 400),
                        (200, 200, 200),
                    )

            # State 3: Main Gameplay
            else:
                self.display.fill((0, 0, 0, 0))
                self.display_2.blit(self.assets["background"], (0, 0))

                self.screenshake = max(0, self.screenshake - 1)

                if not len(self.enemies) and not len(self.blobs) and not self.dead:
                    if self.level == self.num_levels - 1:
                        if not self.game_completed:
                            self.game_completed = True
                            self.completion_time = (
                                pygame.time.get_ticks() - self.start_time
                            )
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
                        self.blobs_defeated += 1
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
                        self.enemies_defeated += 1
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

                # ... (rest of your projectile, spark, particle, and rendering logic is mostly fine) ...
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
                        glow_surf.fill(
                            (255, 60, 60), special_flags=pygame.BLEND_RGB_MULT
                        )
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
                            and abs(self.player.dashing)
                            < self.player.dash_duration - 10
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
                        particle.pos[0] += (
                            math.sin(particle.animation.frame * 0.035) * 0.3
                        )
                    if kill:
                        self.particles.remove(particle)

                # Final rendering to the screen
                self.display_2.blit(self.display, (0, 0))
                screenshake_offset = (
                    random.random() * self.screenshake - self.screenshake / 2,
                    random.random() * self.screenshake - self.screenshake / 2,
                )
                self.screen.blit(
                    pygame.transform.scale(self.display_2, self.screen.get_size()),
                    screenshake_offset,
                )

                # UI Rendering
                health_bar_bg = pygame.Rect(10, 10, 200, 18)
                health_ratio = self.player.health / self.player.maxhealth
                current_health_width = int(200 * health_ratio)
                current_health_bar = pygame.Rect(10, 10, current_health_width, 18)
                pygame.draw.rect(self.screen, (150, 0, 0), health_bar_bg)
                if current_health_width > 0:
                    pygame.draw.rect(self.screen, (0, 255, 0), current_health_bar)
                self.render_text_with_outline(
                    f"AMMO: {self.player.ammo}/{self.player.max_ammo}",
                    self.ui_font,
                    (10, 35),
                    (255, 255, 255),
                )
                self.render_text_with_outline(
                    f"HP: {int(self.player.health)}/{self.player.maxhealth}",
                    self.ui_font,
                    (220, 11),
                    (255, 255, 255),
                )
                self.render_text_with_outline(
                    f"Level: {self.level + 1} / {self.num_levels}",
                    self.ui_font,
                    (10, 60),
                    (255, 255, 255),
                )
                enemies_text_surf = self.ui_font.render(
                    f"Enemies Left: {len(self.enemies)}", True, (255, 255, 255)
                )
                enemies_text_rect = enemies_text_surf.get_rect(
                    topright=(self.screen.get_width() - 10, 10)
                )
                self.render_text_with_outline(
                    f"Enemies Left: {len(self.enemies)}",
                    self.ui_font,
                    enemies_text_rect.topleft,
                    (255, 255, 255),
                )

                if not self.game_completed:
                    elapsed_time = pygame.time.get_ticks() - self.start_time
                else:
                    elapsed_time = self.completion_time
                seconds = int(elapsed_time / 1000) % 60
                minutes = int(elapsed_time / 60000)
                timer_str = f"Time: {minutes:02}:{seconds:02}"
                timer_rect = self.ui_font.render(
                    timer_str, True, (255, 255, 255)
                ).get_rect(
                    topright=(enemies_text_rect.right, enemies_text_rect.bottom + 5)
                )
                self.render_text_with_outline(
                    timer_str, self.ui_font, timer_rect.topleft, (255, 255, 255)
                )
                if self.player.ammo == 0:
                    reload_str = "PRESS R TO RELOAD (-20 HP)"
                    reload_rect = self.ui_font.render(
                        reload_str, True, (255, 220, 220)
                    ).get_rect(
                        center=(
                            self.screen.get_width() // 2,
                            self.screen.get_height() - 30,
                        )
                    )
                    self.render_text_with_outline(
                        reload_str, self.ui_font, reload_rect.topleft, (255, 220, 220)
                    )

            # ================================================================= #
            # 3. FINAL UPDATE AND ASYNCIO YIELD (Happens every frame)
            # ================================================================= #
            pygame.display.update()
            self.clock.tick(60)

            # This is the most important line for web compatibility!
            await asyncio.sleep(0)

        # This will run when the 'running' loop ends
        pygame.quit()


# This is the new entry point for your game
if __name__ == "__main__":
    game_instance = Game()
    asyncio.run(game_instance.main())

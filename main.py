import pygame
import random
import os
import math
import asyncio
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60

#MOBILE UI SETTINGS
JOYSTICK_RADIUS = 60
JOYSTICK_KNOB_RADIUS = 25

BUTTON_SIZE = 70
BUTTON_PADDING = 20
TOUCH_DEADZONE = 0.2


BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
DARK_GRAY = (50, 50, 50)
LIGHT_GRAY = (150, 150, 150)

PLAYER_MAX_HP = 100
PLAYER_SPEED = 5
PLAYER_ROTATION_SPEED = 4
PLAYER_BULLET_SPEED = 12
PLAYER_FIRE_COOLDOWN = 150
PLAYER_MAX_AMMO = 100
PLAYER_RELOAD_TIME = 5000
PLAYER_BULLET_DAMAGE = 50
PLAYER_GRENADE_DAMAGE = 250

PLAYER_MAX_GRENADES = 10
PLAYER_GRENADE_COOLDOWN = 300
PLAYER_GRENADE_SPEED = 10

PICKUP_SPAWN_DELAY = 10000
PICKUP_LIFETIME = 15000
MAX_PICKUPS = 2
PICKUP_RADIUS = 16

ENEMY_SPEED = 2.5
ENEMY_FIRE_DELAY = 1500
ENEMY_BULLET_SPEED = 8
ENEMY_BULLET_DAMAGE_BASE = 10
ENEMY_COLLISION_DAMAGE = 30
ENEMY_MAX_ACTIVE = 3
ENEMY_SPAWN_DELAY = 1300

BANZAI_SPEED = 7.0
BANZAI_DAMAGE = 40
WAVE_1_TARGET = 10
WAVE_2_TARGET = 25
WAVE_3_TARGET = 50

OFFICER_HP = 1200
OFFICER_LASER_DAMAGE = 1

BOSS_HP = 35000
BOSS_BASE_DR = 0.6

#ATTACK IDENTIFIERS
ATK_LINEAR = "linear"
ATK_HOMING = "homing"
ATK_MINION = "minion"

BOX_COOLDOWN_TIME = 30000

PLAYER_LIVES = 1          #1 extra life
INVINCIBLE_TIME = 3000    #3 seconds after dying
DASH_SPEED = 12           
DASH_DURATION = 200       
DASH_COOLDOWN = 1500     

KILLS_PER_WAVE = 10


class GameState(Enum):
    MENU = 1
    PLAYING = 2
    GAME_OVER = 3


@dataclass
class Position:
    x: float
    y: float

    def distance_to(self, other: "Position") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


class Particle:
    def __init__(self, x: float, y: float, vx: float, vy: float, color: Tuple[int, int, int]):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.lifetime = 30
        self.age = 0
        self.size = random.randint(2, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.age += 1
        self.vx *= 0.95
        self.vy *= 0.95

    def is_dead(self) -> bool:
        return self.age >= self.lifetime

    def draw(self, screen: pygame.Surface):
        alpha = int(255 * (1 - self.age / self.lifetime))
        size = max(1, int(self.size * (1 - self.age / self.lifetime)))
        if alpha > 0:
            surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*self.color, alpha), (size, size), size)
            screen.blit(surf, (int(self.x - size), int(self.y - size)))


#MOBILE UI CLASSES 

class MobileButton:
    def __init__(self, x, y, size, label, color=(50, 150, 255)):
        self.rect = pygame.Rect(x, y, size, size)
        self.label = label
        self.color = color
        self.last_used = 0
        self.cooldown = 0

    def ready(self):
        return pygame.time.get_ticks() - self.last_used >= self.cooldown

    def draw(self, screen, font):
        pygame.draw.circle(screen, self.color, self.rect.center, self.rect.width//2)
        text = font.render(self.label, True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=self.rect.center))

        if self.cooldown > 0 and not self.ready():
            pct = (pygame.time.get_ticks() - self.last_used) / self.cooldown
            pygame.draw.arc(
                screen, (255, 255, 255),
                self.rect.inflate(-6, -6),
                -math.pi/2,
                -math.pi/2 + pct * 2 * math.pi,
                4
            )


class VirtualJoystick:
    def __init__(self, x, y):
        self.base = pygame.Vector2(x, y)
        self.knob = pygame.Vector2(x, y)
        self.active = False
        self.vector = pygame.Vector2(0, 0)

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.base.distance_to(event.pos) <= JOYSTICK_RADIUS:
                self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
            self.knob = self.base
            self.vector.update(0, 0)
        elif event.type == pygame.MOUSEMOTION and self.active:
            delta = pygame.Vector2(event.pos) - self.base
            if delta.length() > JOYSTICK_RADIUS:
                delta.scale_to_length(JOYSTICK_RADIUS)
            self.knob = self.base + delta
            self.vector = delta / JOYSTICK_RADIUS

    def draw(self, screen):
        pygame.draw.circle(screen, (40, 40, 40), self.base, JOYSTICK_RADIUS)
        pygame.draw.circle(screen, (180, 180, 180), self.knob, JOYSTICK_KNOB_RADIUS)


class Bullet:
    def __init__(self, x: float, y: float, vx: float, vy: float, is_player: bool, is_grenade: bool = False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.is_player = is_player
        self.is_grenade = is_grenade
        if self.is_grenade:
            self.width = 12
            self.height = 8
        else:
            self.width = 8
            self.height = 3
        self.active = True

    def update(self):
        self.x += self.vx
        self.y += self.vy

        if self.x < -50 or self.x > SCREEN_WIDTH + 50:
            self.active = False
        if self.y < -50 or self.y > SCREEN_HEIGHT + 50:
            self.active = False

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - self.width // 2, self.y - self.height // 2,
                           self.width, self.height)

    def draw(self, screen: pygame.Surface):
        #DRAW TRAILS(For Doritos)
        if self.width == 16:
            #Draw a faint line behind the bullet
            pygame.draw.line(screen, (255, 100, 0), (self.x, self.y), (self.x - self.vx*3, self.y - self.vy*3), 2)

        #DRAW SHAPES
        if self.width == 16: #Dorito Triangle
            angle = math.atan2(self.vy, self.vx)
            p1 = (self.x + math.cos(angle) * 15, self.y + math.sin(angle) * 15)
            p2 = (self.x + math.cos(angle + 2.5) * 10, self.y + math.sin(angle + 2.5) * 10)
            p3 = (self.x + math.cos(angle - 2.5) * 10, self.y + math.sin(angle - 2.5) * 10)
            pygame.draw.polygon(screen, ORANGE, [p1, p2, p3])
        elif self.width == 12: #Super Bullet (Non-Homing Circle)
            pygame.draw.circle(screen, YELLOW, (int(self.x), int(self.y)), 6)
        else: #Standard
            color = ORANGE if self.is_grenade else (YELLOW if self.is_player else RED)
            pygame.draw.rect(screen, color, self.get_rect())


class Pickup:
    def __init__(self, x: float, y: float, radius: int = PICKUP_RADIUS):
        self.x = x
        self.y = y
        self.radius = radius
        self.spawn_time = pygame.time.get_ticks()
        self.active = True
        self.color = BLUE

    def is_expired(self, current_time: int) -> bool:
        return (current_time - self.spawn_time) >= PICKUP_LIFETIME

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)

    def draw(self, screen: pygame.Surface):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, LIGHT_GRAY, (int(self.x), int(self.y)), max(2, self.radius // 4))


class PlayerJet:
    def __init__(self, image: pygame.Surface):
        self.x = 150.0
        self.y = SCREEN_HEIGHT // 2.0
        self.angle = 0.0
        self.original_image = image
        self.width = 50
        self.height = 30
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.last_shot_time = 0
        self.hit_flash_timer = 0

        self.ammo = PLAYER_MAX_AMMO
        self.max_ammo = PLAYER_MAX_AMMO
        self.is_reloading = False
        self.reload_start_time = 0

        self.grenades = 0
        self.max_grenades = PLAYER_MAX_GRENADES
        self.last_grenade_time = 0

        self.lives = PLAYER_LIVES
        self.invincible_timer = 0
        self.is_dashing = False
        self.dash_start_time = 0
        self.last_dash_time = 0
        self.dash_direction = (0, 0)
        self.invincible_cheat = False
        self.regen_end_time = 0

    def move(self, dx: float, dy: float, current_time: int, dash_pressed: bool, joystick_vector: pygame.Vector2):
        #Handle Dash Initialization
        if dash_pressed and not self.is_dashing and current_time - self.last_dash_time > DASH_COOLDOWN:
            if dx != 0 or dy != 0:
                self.is_dashing = True
                self.dash_start_time = current_time
                self.last_dash_time = current_time
                self.dash_direction = (dx, dy)

        #Calculate Movement
        if self.is_dashing:
            if current_time - self.dash_start_time < DASH_DURATION:
                self.x += self.dash_direction[0] * DASH_SPEED
                self.y += self.dash_direction[1] * DASH_SPEED
            else:
                self.is_dashing = False
        else:
            #Keyboard Movement
            self.x += dx * PLAYER_SPEED
            self.y += dy * PLAYER_SPEED
            
            #Mobile Joystick Movement
            self.x += joystick_vector.x * PLAYER_SPEED
            self.y += joystick_vector.y * PLAYER_SPEED

        #Keep on screen
        self.x = max(self.width // 2, min(SCREEN_WIDTH - self.width // 2, self.x))
        self.y = max(self.height // 2, min(SCREEN_HEIGHT - self.height // 2, self.y))

    def rotate(self, direction: int):
        self.angle += direction * PLAYER_ROTATION_SPEED
        self.angle = self.angle % 360

    def shoot(self, current_time: int) -> Optional[Bullet]:
        if self.is_reloading:
            if current_time - self.reload_start_time >= PLAYER_RELOAD_TIME:
                self.is_reloading = False
                self.ammo = self.max_ammo
            else:
                return None

        if self.ammo <= 0:
            self.is_reloading = True
            self.reload_start_time = current_time
            return None

        if current_time - self.last_shot_time >= PLAYER_FIRE_COOLDOWN:
            self.last_shot_time = current_time
            self.ammo -= 1

            angle_rad = math.radians(self.angle)
            nose_offset = self.width // 2
            bullet_x = self.x + math.cos(angle_rad) * nose_offset
            bullet_y = self.y + math.sin(angle_rad) * nose_offset

            vx = math.cos(angle_rad) * PLAYER_BULLET_SPEED
            vy = math.sin(angle_rad) * PLAYER_BULLET_SPEED

            return Bullet(bullet_x, bullet_y, vx, vy, True)
        return None

    def fire_grenade(self, current_time: int) -> Optional[Bullet]:
        if self.grenades <= 0:
            return None
        if current_time - self.last_grenade_time < PLAYER_GRENADE_COOLDOWN:
            return None
        self.last_grenade_time = current_time
        self.grenades -= 1

        angle_rad = math.radians(self.angle)
        nose_offset = self.width // 2
        gx = self.x + math.cos(angle_rad) * nose_offset
        gy = self.y + math.sin(angle_rad) * nose_offset

        vx = math.cos(angle_rad) * PLAYER_GRENADE_SPEED
        vy = math.sin(angle_rad) * PLAYER_GRENADE_SPEED

        return Bullet(gx, gy, vx, vy, True, is_grenade=True)

    def take_damage(self, damage: int):
        self.hp -= damage
        self.hit_flash_timer = 10
        if self.hp < 0:
            self.hp = 0

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - self.width // 2, self.y - self.height // 2,
                           self.width, self.height)

    def draw(self, screen: pygame.Surface, current_time: int):
        #Flicker if invincible
        if self.invincible_timer > current_time:
            if (current_time // 100) % 2 == 0:
                return #Skip drawing this frame to flicker

        rotated_image = pygame.transform.rotate(self.original_image, -self.angle)
        if self.hit_flash_timer > 0:
            rotated_image = rotated_image.copy()
            rotated_image.fill((255, 100, 100), special_flags=pygame.BLEND_ADD)
            self.hit_flash_timer -= 1

        rect = rotated_image.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated_image, rect)


class EnemyJet:
    def __init__(self, x: float, y: float, wave: int, image: pygame.Surface, is_banzai=False):
        self.x = x
        self.y = y
        self.is_banzai = is_banzai
        self.angle = 180.0
        self.original_image = image
        self.width, self.height = 45, 28
        self.hp = 80 if is_banzai else 150 #Banzais are faster but easier to kill
        self.max_hp = self.hp
        self.last_shot_time = 0
        self.active = True
        self.sine_offset = random.uniform(0, 100) #So they aren't in a straight line
        self.sine_amplitude = random.uniform(2, 8) #Some zigzag wide, some small
        self.sine_speed = random.uniform(0.003, 0.008) #Some zigzag fast, some slow
        
        self.fire_delay = max(800, ENEMY_FIRE_DELAY - (wave - 1) * 200)
        self.wave = wave
        
        #Stats based on wave
        self.speed = ENEMY_SPEED + (wave * 0.5)
        if self.is_banzai:
            self.speed = BANZAI_SPEED
            self.hp = 80 
            #Make a unique copy so only this one turns red, not all enemies
            self.original_image = image.copy() 
            self.original_image.fill((255, 50, 50), special_flags=pygame.BLEND_RGB_ADD)

    def update(self, player_x: float, player_y: float):
        #Banzai planes fly straight fast
        if self.is_banzai:
            #If the plane is in front of you, track you
            if self.x > player_x - 30:
                dx = player_x - self.x
                dy = player_y - self.y
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist > 135: 
                    self.x += (dx/dist) * self.speed
                    self.y += (dy/dist) * self.speed
                    self.angle = math.degrees(math.atan2(dy, dx))
                else:
                    #Fly straight
                    rad = math.radians(self.angle)
                    self.x += math.cos(rad) * self.speed
                    self.y += math.sin(rad) * self.speed
            else:
                #Rocket straight
                rad = math.radians(self.angle)
                self.x += math.cos(rad) * self.speed
                self.y += math.sin(rad) * self.speed
        else:
            #Normal enemy behavior
            self.x -= self.speed
            dy = player_y - self.y
            if abs(dy) > 5:
                #Normal jets in wave 2/3 tracks much faster
                tracking_speed = 2.5 if self.wave >= 3 else 1.8 if self.wave == 2 else 1.0
                self.y += tracking_speed if dy > 0 else -tracking_speed
                
            #Wave 3 Zig-zagging (just Sine Wave)
            if self.wave >= 3:
                #Use the random variables for a "Drunken/Unpredictable" flight path
                self.y += math.sin((pygame.time.get_ticks() + self.sine_offset) * self.sine_speed) * self.sine_amplitude
        
        if (self.x < -100 or self.x > SCREEN_WIDTH + 150 or 
            self.y < -100 or self.y > SCREEN_HEIGHT + 100):
            self.active = False
            return "escaped"
        
        return "alive"

    def try_shoot(self, current_time: int, player_x: float, player_y: float) -> Optional[Bullet]:
        if self.x < player_x:
            return None

        if current_time - self.last_shot_time >= self.fire_delay:
            self.last_shot_time = current_time

            angle_rad = math.radians(self.angle)
            nose_offset = self.width // 2
            bullet_x = self.x + math.cos(angle_rad) * nose_offset
            bullet_y = self.y + math.sin(angle_rad) * nose_offset

            dx = player_x - bullet_x
            dy = player_y - bullet_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                vx = (dx / dist) * ENEMY_BULLET_SPEED
                vy = (dy / dist) * ENEMY_BULLET_SPEED
            else:
                vx = -ENEMY_BULLET_SPEED
                vy = 0

            return Bullet(bullet_x, bullet_y, vx, vy, False)
        return None

    def take_damage(self, damage: int):
        self.hp -= damage
        if self.hp <= 0:
            self.active = False

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - self.width // 2, self.y - self.height // 2,
                           self.width, self.height)

    def draw(self, screen: pygame.Surface):
        rotated_image = pygame.transform.rotate(self.original_image, -self.angle)
        rect = rotated_image.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated_image, rect)

        hp_ratio = max(0.0, self.hp / self.max_hp)
        bar_width = self.width
        bar_height = 4
        bar_x = self.x - bar_width // 2
        bar_y = self.y - self.height // 2 - 10

        pygame.draw.rect(screen, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, GREEN, (bar_x, bar_y, int(bar_width * hp_ratio), bar_height))


class Officer(EnemyJet):
    def __init__(self, x, y, image, role="main"):
        super().__init__(x, y, 4, image)
        self.role = role
        self.role_index = 0 
        self.hp = OFFICER_HP
        self.max_hp = OFFICER_HP
        self.state = "erratic"
        self.timer = pygame.time.get_ticks()
        self.laser_circle_rad = 0
        self.is_firing = False
        self.move_target_y = y

    def update(self, player_x, player_y, game_ref=None):
        now = pygame.time.get_ticks()

        #OFFICER SURVIVOR / PROMOTION LOGIC
        if game_ref:
            #Wave 4 Officer's if I am a Sub and my partner died, I become Main.
            if self.role in ["sub", "sub_top", "sub_bot"]:
                alive_officers = [o for o in game_ref.officers if o.role in ["main", "sub", "sub_top", "sub_bot"]]
                if len(alive_officers) == 1:
                    self.role = "main"

            #Boss Phase Officer's if I am a Guard...
            if self.role == "guard":
                #Ensure Officer positioned INSIDE the shield , not outside
                if game_ref.boss:
                     self.x = game_ref.boss.x - 150
                
                #If my partner died, I take Center Target
                guards = [o for o in game_ref.officers if o.role == "guard"]
                if len(guards) == 1:
                    self.role_index = 0

        #SCARE SEQUENCE (Wave 5)
        if self.role == "scare":
            if self.state == "winding" or self.is_firing: return "alive"
            if hasattr(self, 'target_pos'):
                self.x += (self.target_pos[0] - self.x) * 0.1
                self.y += (self.target_pos[1] - self.y) * 0.1
                if abs(self.x - self.target_pos[0]) < 5:
                    self.y += math.sin(now * 0.005) * 1.5
            return "alive"
        elif self.role == "rocket":
            self.x += 25; return "alive"

        #WAVE 4 ENTRY LOGIC
        #Fly onto the screen if I just spawned
        if self.role in ["main", "sub", "sub_top", "sub_bot"]:
            target_x = SCREEN_WIDTH - 200
            if self.x > target_x: self.x -= 4

        #TARGETING LOGIC
        target_y = player_y
        
        #Specific Offsets for Subs
        if self.role == "sub_top": target_y = player_y - 150
        if self.role == "sub_bot": target_y = player_y + 150
        
        #Boss Guard Targeting
        if self.role == "guard":
            #essentially, Index 0 = Center (Player), Index 1 = Offset
            if self.role_index == 1:
                target_y = player_y + 200 if player_y < SCREEN_HEIGHT//2 else player_y - 200

        #STATE MACHINE (MOVEMENT & FIRING)
        if self.state == "erratic":
            if now - self.timer > 1000:
                self.move_target_y = random.randint(100, SCREEN_HEIGHT-100)
                self.state = "steady"; self.timer = now
            if not self.is_firing: self.y += (self.move_target_y - self.y) * 0.05
            
        elif self.state == "steady":
            if now - self.timer > 1500: self.state = "winding"; self.timer = now
            if not self.is_firing: self.y += (target_y - self.y) * 0.05
                
        elif self.state == "winding":
            if not self.is_firing: self.y += (target_y - self.y) * 0.03
            self.laser_circle_rad += 1.0
            if self.laser_circle_rad > 40: self.state = "firing"; self.timer = now
                
        elif self.state == "firing":
            self.is_firing = True
            if now - self.timer > 2500:
                self.state = "erratic"; self.is_firing = False; self.laser_circle_rad = 0; self.timer = now
        
        return "alive"


    def draw(self, screen):
        #If an image was provided, draw it... otherwise use fallback rect UI
        if self.original_image:
            rotated = pygame.transform.rotate(self.original_image, -self.angle)
            rect = rotated.get_rect(center=(int(self.x), int(self.y)))
            screen.blit(rotated, rect)
        else:
            rect = pygame.Rect(self.x-30, self.y-30, 60, 60)
            pygame.draw.rect(screen, LIGHT_GRAY, rect, border_radius=10)
            pygame.draw.rect(screen, BLUE, rect, 3, border_radius=10)

        hp_w = 60 * (self.hp / self.max_hp)
        pygame.draw.rect(screen, RED, (self.x-30, self.y-45, hp_w, 5))

        if self.state == "winding":
            radius = (pygame.time.get_ticks() / 10) % 40
            pygame.draw.circle(screen, WHITE, (int(self.x-30), int(self.y)), int(radius), 2)
            
        if self.is_firing:
            lx = self.x - 30
            pygame.draw.line(screen, (0, 100, 255), (lx, self.y), (0, self.y), 15)
            pygame.draw.line(screen, WHITE, (lx, self.y), (0, self.y), 5)

        if hasattr(self, 'show_alert'):
            if self.show_alert == "solid":
                font = pygame.font.SysFont("Arial", 40, bold=True)
                txt = font.render("!", True, YELLOW)
                screen.blit(txt, (self.x - 5, self.y - 70))
            elif self.show_alert == "flicker":
                if (pygame.time.get_ticks() // 100) % 2 == 0:
                    font = pygame.font.SysFont("Arial", 40, bold=True)
                    txt = font.render("!", True, RED)
                    screen.blit(txt, (self.x - 5, self.y - 70))


    def check_laser_hit(self, player_rect):
        if self.is_firing:
            if player_rect.top < self.y + 25 and player_rect.bottom > self.y - 25:
                if player_rect.right < self.x: 
                    return True
        return False


class SquareExplosion:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.life = 0
        self.max_life = random.randint(30, 50)
        self.angle = random.randint(0, 90)
        self.target_size = random.randint(20, 150)
        self.color = random.choice([(255, 50, 50), (255, 150, 0), (255, 255, 255)])
    
    def update(self):
        self.life += 1
        
    def draw(self, screen):
        progress = self.life / self.max_life
        if progress < 0.5:
            current_size = self.target_size * (progress * 2)
        else:
            current_size = self.target_size * (1 - (progress - 0.5) * 2)
            
        if current_size > 0:
            s = pygame.Surface((int(current_size), int(current_size)))
            s.fill(self.color)
            s.set_alpha(200)
            s = pygame.transform.rotate(s, self.angle + (self.life * 2))
            rect = s.get_rect(center=(self.x, self.y))
            screen.blit(s, rect)


class Boss:
    def __init__(self):
        self.x = SCREEN_WIDTH + 500
        self.y = 0 
        self.hp = BOSS_HP
        self.max_hp = BOSS_HP
        self.is_entering = True 
        self.bar_fill = 0.0 
        self.hit_timer = 0
        
        self.shoot_origin_x = SCREEN_WIDTH - 150
        
        self.state = "IDLE" 
        self.state_timer = 0
        self.damage_reduction = BOSS_BASE_DR
        
        self.current_phase = 1 
        
        #ATTACK LOGIC
        self.attack_history = []
        self.current_attack = None
        self.attacks_performed = 0
        self.attacks_until_super = random.randint(3, 5)
        
        self.secondary_attack = None
        self.secondary_fire_timer = 0
        self.officer_respawn_timer = 0

        self.fire_timer = 0
        self.color_override = None

        self.red_tint = False
        self.coil = None
        self.shield_active = False
        self.last_stand_timer = 0
        self.white_flash = 0

        #BERSERK and DEATH VARIABLES
        self.has_gone_berserk = False
        self.berserk_invincible_timer = 0
        self.final_laser_rect = None

        self.death_fx = [] #List for square explosions
        self.fall_rotation = 0 #For the "crooked" fall

        try:
            img = pygame.image.load("assetjet/boss.png").convert_alpha()
            self.image = pygame.transform.scale(img, (200, 1500))
        except Exception:
            self.image = None

    def decide_attack(self):
        #BERSERK LOGIC
        if self.has_gone_berserk:
            if self.last_attack_was_ult:
                self.last_attack_was_ult = False
                return "BERSERK_BARRAGE"
            else:
                self.last_attack_was_ult = True
                # Pick an Ult(Mega Laser or Super Charge)
                return random.choice(["MEGA_LASER_START", "SUPER_CHARGE"])

        #Force Mega Laser if it's the first attack after stagger
        if hasattr(self, 'current_attack') and self.current_attack == "MEGA_LASER":
            return "MEGA_LASER_START"

        if self.attacks_performed >= self.attacks_until_super:
            #60% Chance of Mega Laser vs 40% Chance of Spinning Circles
            if self.current_phase >= 2 and random.random() < 0.6:
                return "MEGA_LASER_START"
            return "SUPER_CHARGE"

        #3 Attack types
        pool = [ATK_LINEAR, ATK_HOMING, ATK_MINION]
        
        #BOSS PHASE 3... Pick TWO different attacks
        if self.current_phase >= 3:
            chosen = random.sample(pool, 2)
            self.secondary_attack = chosen[1]
            return chosen[0]

        if len(self.attack_history) >= 2:
            if self.attack_history[-1] == self.attack_history[-2]:
                pool = [a for a in pool if a != self.attack_history[-1]]
            self.secondary_attack = None
        return random.choice(pool)

    def update(self, player_x, player_y, game_ref):
        now = pygame.time.get_ticks()

        if self.state in ["DYING_STILL", "DYING_WINDUP", "DYING_LASER", "FALLING"]:
            self.hp = 1 #Lock HP
            self.damage_reduction = 1.0 #Lock Invincibility
            
            if self.state == "DYING_STILL":
                game_ref.enemies.clear(); game_ref.officers.clear()
                if now > self.state_timer:
                    self.state = "DYING_WINDUP"; self.state_timer = now + 3000

            elif self.state == "DYING_WINDUP":
                game_ref.screen_shake(5)
                if now > self.state_timer:
                    self.state = "DYING_LASER"; self.state_timer = now + 4000
                    game_ref.screen_shake(50)

            elif self.state == "DYING_LASER":
                kill_zone = pygame.Rect(0, 150, SCREEN_WIDTH, SCREEN_HEIGHT - 300)
                if game_ref.player.get_rect().colliderect(kill_zone):
                    game_ref.player.take_damage(1000) 
                
                #Explosions
                if random.random() < 0.3:
                    self.death_fx.append(SquareExplosion(self.x + random.randint(-150, 150), self.y + random.randint(0, 800)))

                if now > self.state_timer:
                    self.state = "FALLING"

            elif self.state == "FALLING":
                self.x += 1.0; self.y += 3.0; self.fall_rotation += 0.5 
                if random.random() < 0.5:
                    self.death_fx.append(SquareExplosion(self.x + random.randint(-100, 100), self.y + random.randint(0, 600)))

                if self.y > SCREEN_HEIGHT + 800:
                    game_ref.boss = None; game_ref.boss_defeated = True
                    game_ref.victory_timer = pygame.time.get_ticks()

            for fx in self.death_fx[:]:
                fx.update()
                if fx.life >= fx.max_life: self.death_fx.remove(fx)
            
            return
        
        #DEATH TRIGGER CHECK
        if self.hp <= 0 and self.has_gone_berserk:
             self.state = "DYING_STILL"
             self.state_timer = now + 1000
             game_ref.enemies.clear()
             return

        #BERSERK TRIGGER
        if self.hp <= (self.max_hp * 0.05) and not self.has_gone_berserk:
            self.has_gone_berserk = True
            self.hp = self.max_hp * 0.10 #Heal back to 10%
            self.state = "IDLE"
            self.state_timer = now + 500
            self.berserk_invincible_timer = now + 5000 #5s Invincibility
            self.damage_reduction = 1.0  #Invincible
            self.last_attack_was_ult = False
            game_ref.create_explosion(self.x, self.y, RED)
            game_ref.screen_shake(50)
            print("BERSERK ACTIVATED!")

        #BERSERK OVERRIDES
        if self.has_gone_berserk:
            self.color_override = (255, 50, 50)
            self.red_tint = True
            if now < self.berserk_invincible_timer:
                self.damage_reduction = 1.0
            else:
                self.damage_reduction = 0.9

        if self.is_entering:
            self.x -= 2.0; self.bar_fill = min(1.0, self.bar_fill + 0.01)
            if self.x <= SCREEN_WIDTH - 250 : self.is_entering = False
            return

        #GLOBAL SPEED NERFS
        target_y = max(-250, min(250, player_y - 350))

        self.y += (target_y - self.y) * 0.001 

        if self.hit_timer > 0: self.hit_timer -= 1

        if not self.is_entering and self.state != "STUNNED":
            target_y = max(-250, min(250, player_y - 350))
            self.y += (target_y - self.y) * 0.0001

        #PHASE 2 STAGGER TRIGGER (66% HP)
        if self.current_phase == 1 and self.hp < (self.max_hp * 0.66):
            self.current_phase = 2
            self.state = "STAGGERED"
            self.state_timer = now + 1500
            self.damage_reduction = 1.0 
            self.mega_laser_unlocked = True
            self.skip_stun_once = True #First Mega Laser shall not stun
            return

        #STAGGER SEQUENCE LOGIC
        if self.state == "STAGGERED":
            self.y += (0 - self.y) * 0.2
            # Violent vibration
            self.hit_timer = 5 
            game_ref.screen_shake(15)
            #White Flash near end
            if now > self.state_timer - 200:
                self.color_override = WHITE
            if now > self.state_timer:
                self.color_override = None
                if self.current_phase == 4:
                    #START LAST STAND
                    self.state = "LAST_STAND"
                    self.shield_active = True
                    self.coil = Coil(self.x - 300, self.y + 350)
                    #Force spawn 2 Officers immediately (use officer image)
                    game_ref.officers.clear()
                    game_ref.officers.append(Officer(self.x-200, self.y+200, game_ref.officer_image, "main"))
                    game_ref.officers.append(Officer(self.x-200, self.y+500, game_ref.officer_image, "sub_bot"))
                else:
                    self.state = "CHARGING" 
                    self.state_timer = now + 1000
                    self.current_attack = "MEGA_LASER"
            return

            if now > self.state_timer:
                if self.current_phase == 4:
                    self.state = "LAST_STAND"
                    self.shield_active = True
                    self.coil = Coil(self.x - 300, self.y + 350)
                else:
                    self.state = "CHARGING"

        #MEGA LASER ATTACK STATES
        if self.state == "MEGA_LASER_FIRE":
            #Slow homing while firing unlike officer's static firing
            target_y = max(-250, min(250, player_y - 350))
            self.y += (target_y - self.y) * 0.005
            
            #Damage Logic
            p_rect = game_ref.player.get_rect()
            if p_rect.top < (self.y + 350) + 25 and p_rect.bottom > (self.y + 350) - 25:
                if p_rect.right < self.x and not game_ref.player.invincible_cheat:
                    game_ref.player.take_damage(1.5)

            if now > self.state_timer:
                self.current_attack = None 

                #BERSERK: Never Stun
                if self.has_gone_berserk:
                    self.state = "IDLE"
                    self.state_timer = now + 500
                #PHASE 2 INTRO: Skip Stun Once
                elif self.skip_stun_once:
                    self.state = "IDLE"
                    self.skip_stun_once = False
                    self.state_timer = now + 500
                #NORMAL: Get Stunned
                else:
                    self.state = "STUNNED"
                    self.state_timer = now + 5000
            return
        #PHASE 3 TRIGGER (33% HP)
        if self.current_phase == 2 and self.hp < (self.max_hp * 0.33):
            self.current_phase = 3
            self.state = "STAGGERED"
            self.state_timer = now + 1500
            self.damage_reduction = 1.0 
            return

        #PHASE 3 PASSIVE'S Guard Officer Spawning
        if self.current_phase == 3:
            if len(game_ref.officers) == 0 and now > self.officer_respawn_timer:
                new_guard = Officer(self.x - 200, self.y + 350, game_ref.officer_image, "guard")
                game_ref.officers.append(new_guard)

        #PHASE 4 TRIGGER (10% HP)
        if self.current_phase == 3 and self.hp < (self.max_hp * 0.10):
            self.current_phase = 4
            self.state = "STAGGERED"
            self.state_timer = now + 2000
            self.red_tint = True
            self.damage_reduction = 1.0 
            return

        if self.state == "LAST_STAND":
            self.damage_reduction = 1.0 #Immune while shield is up
            #Passive Attack
            if now > self.fire_timer:
                dy_top = (player_y - (self.y + 110)) * 0.02
                dy_bot = (player_y - (self.y + 590)) * 0.02
                for spread in [-1.5, 1.5]: # 2 bullet spread
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 110, -10, dy_top + spread, False))
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 590, -14, dy_bot + spread, False))
                self.fire_timer = now + 1000

            #Respawn 2 Officers if dead
            if len(game_ref.officers) < 2 and now > self.officer_respawn_timer:
                off1 = Officer(self.x-200, self.y+200, game_ref.officer_image, "guard")
                off1.role_index = 0
                off2 = Officer(self.x-200, self.y+500, game_ref.officer_image, "guard")
                off2.role_index = 1
                game_ref.officers.extend([off1, off2])
            return

        #STATE MACHINE
        if self.state == "IDLE":
            self.damage_reduction = BOSS_BASE_DR
            self.color_override = None
            
            self.y += (0 - self.y) * 0.05

            if now > self.state_timer:
                decision = self.decide_attack()
                if decision == "MEGA_LASER_START":
                    self.state = "CHARGING"
                    self.current_attack = "MEGA_LASER"
                    self.state_timer = now + 2000
                elif decision == "SUPER_CHARGE":
                    self.state = "CHARGING"
                    self.state_timer = now + 1500 
                else:
                    self.current_attack = decision
                    self.state = "WINDUP"
                    self.state_timer = now + 1000 
        
        elif self.state == "WINDUP":
            target_y = max(-200, min(200, player_y - 350))
            self.y += (target_y - self.y) * 0.02 
            
            if now > self.state_timer:
                self.state = "EXECUTING"
                self.state_timer = now + 2000
                
        elif self.state == "EXECUTING":
            target_y = max(-250, min(250, player_y - 350))
            self.y += (target_y - self.y) * 0.002 

            #LINEAR ATTACK
            if self.current_attack == ATK_LINEAR:
                if now > self.fire_timer:
                    #Calculate trajectory specifically from each engine towards player
                    dy_top = (player_y - (self.y + 110)) * 0.02 + random.uniform(-2, 2)
                    dy_bot = (player_y - (self.y + 590)) * 0.02 + random.uniform(-2, 2)
                    
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 110, -14, dy_top, False))
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 590, -14, dy_bot, False))
                    self.fire_timer = now + 80

            #KAMIKAZE DORITOS (Homing Missiles)
            elif self.current_attack == ATK_HOMING:
                if now > self.fire_timer:
                    #Spawn exactly 5 Doritos
                    for i in range(5):
                        # Give them an initial kick
                        initial_vy = (i - 2) * 8 
                        b = Bullet(self.shoot_origin_x, self.y + 350, -6, initial_vy, False)
                        b.width, b.height = 16, 16 
                        
                        b.target_row_y = 100 + (i * 125) 
                        game_ref.bullets.append(b)
                        
                    self.fire_timer = now + 2500 

            #MINION SPAWN ATTACK
            elif self.current_attack == ATK_MINION:
                if now > self.fire_timer:
                    #Spawns fodder using standard wave logic
                    game_ref.spawn_enemy()
                    self.fire_timer = now + 1500 

            #BERSERK BARRAGE (All Attacks At Once)
            elif self.current_attack == "BERSERK_BARRAGE":
                if now > self.fire_timer:
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 110, -14, 0, False))
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 590, -14, 0, False))
                    b = Bullet(self.shoot_origin_x, self.y + 350, -8, random.uniform(-5, 5), False)
                    b.width, b.height = 16, 16
                    game_ref.bullets.append(b)
                    game_ref.screen_shake(2)
                    self.fire_timer = now + 200

            #SECONDARY ATTACK (Phase 3 Only)
            if self.secondary_attack:
                if self.secondary_attack == ATK_LINEAR and now > self.secondary_fire_timer:
                    game_ref.bullets.append(Bullet(self.shoot_origin_x, self.y + 350, -12, random.uniform(-3, 3), False))
                    self.secondary_fire_timer = now + 100
                elif self.secondary_attack == ATK_HOMING and now > self.secondary_fire_timer:
                    b = Bullet(self.shoot_origin_x, self.y + 350, -6, random.uniform(-4, 4), False)
                    b.width, b.height = 16, 16 
                    game_ref.bullets.append(b)
                    self.secondary_fire_timer = now + 800

            #Transition out of Execution
            if now > self.state_timer:
                self.state = "RECOVERY"
                self.state_timer = now + 1000
                self.attack_history.append(self.current_attack)
                self.attacks_performed += 1

        elif self.state == "RECOVERY":
            if now > self.state_timer:
                self.state = "IDLE"
                self.state_timer = now + 500

        elif self.state == "CHARGING":
            self.color_override = (255, 255, 200) 
            if now > self.state_timer:
                if self.current_attack == "MEGA_LASER":
                    self.state = "MEGA_LASER_FIRE"
                    self.state_timer = now + 3000
                else:
                    self.state = "SUPER_EXECUTE"
                    self.state_timer = now + 4000

        elif self.state == "SUPER_EXECUTE":
            if (now // 150) % 2 == 0:
                for i in range(0, 360, 45):
                    rad = math.radians(i + (now * 0.1))
                    b = Bullet(self.shoot_origin_x, self.y + 350, math.cos(rad) * 7, math.sin(rad) * 7, False)
                    b.width, b.height = 12, 12 
                    game_ref.bullets.append(b)
            
            if now > self.state_timer:
                if self.has_gone_berserk:
                    self.state = "IDLE"
                    self.state_timer = now + 500
                else:
                    self.state = "STUNNED"
                    self.state_timer = now + 5000 
                
                game_ref.enemies.clear() 

        #BERSERK STATE (Red, Invincible, Fast)
        elif self.state == "BERSERK":
            self.color_override = (255, 0, 0)
            self.red_tint = True
            # Invincibility Check
            if now < self.berserk_invincible_timer:
                self.damage_reduction = 1.0
            else:
                self.damage_reduction = 0.9
            
            #Spam Super Bullets everywhere
            if (now // 100) % 2 == 0:
                for i in range(0, 360, 30):
                    rad = math.radians(i + (now * 0.3))

                    b = Bullet(self.shoot_origin_x, self.y + 350, math.cos(rad) * 10, math.sin(rad) * 10, False)
                    b.width, b.height = 12, 12; game_ref.bullets.append(b)

        #DEATH SEQUENCE
        elif self.state == "DYING_STILL":
            game_ref.enemies.clear(); game_ref.officers.clear()
            self.damage_reduction = 1.0
            if now > self.state_timer:
                self.state = "DYING_WINDUP"; self.state_timer = now + 3000

        elif self.state == "DYING_WINDUP":
            game_ref.screen_shake(5)
            if now > self.state_timer:
                self.state = "DYING_LASER"; self.state_timer = now + 4000
                game_ref.screen_shake(50)

        elif self.state == "DYING_LASER":
            self.damage_reduction = 1.0
            
            #Massive Damage Zone
            kill_zone = pygame.Rect(0, 150, SCREEN_WIDTH, SCREEN_HEIGHT - 300)
            if game_ref.player.get_rect().colliderect(kill_zone):
                game_ref.player.take_damage(1000) 
            
            #GENERATE SQUARE EXPLOSIONS
            if random.random() < 0.3:
                ex_x = self.x + random.randint(-150, 150)
                ex_y = self.y + random.randint(0, 800)
                self.death_fx.append(SquareExplosion(ex_x, ex_y))

            if now > self.state_timer:
                self.state = "FALLING"

        elif self.state == "FALLING":
            self.x += 1.0
            self.y += 2.0
            self.fall_rotation += 0.2
            
            #Massive explosions during fall
            if random.random() < 0.5:
                self.death_fx.append(SquareExplosion(self.x + random.randint(-100, 100), self.y + random.randint(0, 600)))

            if self.y > SCREEN_HEIGHT + 800:
                game_ref.boss = None
                game_ref.boss_defeated = True
                game_ref.victory_timer = pygame.time.get_ticks() 
        
        elif self.state == "STUNNED":
            self.damage_reduction = 0.0 
            self.color_override = (50, 50, 50) 
            
            if now > self.state_timer:
                self.state = "RECOVERY"
                self.state_timer = now + 1000
                self.attacks_performed = 0 
                self.attacks_until_super = random.randint(3, 5)

        for fx in self.death_fx[:]:
            fx.update()
            if fx.life >= fx.max_life:
                self.death_fx.remove(fx)
            
            #Explosions on boss
            if random.random() < 0.5:
                ex_x = self.x + random.randint(-100, 100)
                ex_y = self.y + random.randint(0, 800)
                game_ref.create_explosion(ex_x, ex_y, RED)

            if now > self.state_timer:
                self.state = "FALLING"


    def draw(self, screen, font):
        shake_x = 0

        #Color Logic
        if self.has_gone_berserk and self.state != "STUNNED":
            #INTENSE FLICKER... (Alternates every 3 frames)
            if (pygame.time.get_ticks() // 50) % 2 == 0:
                body_color = (255, 0, 0)
            else:
                body_color = (139, 0, 0)
        elif self.hit_timer > 0:
            body_color = (200, 50, 50) 
            shake_x = random.randint(-5, 5)
        elif self.red_tint:
            body_color = (120, 30, 40) 
        elif self.state == "STUNNED":
            #Flicker Dark Grey / Light Grey
            if (pygame.time.get_ticks() // 200) % 2 == 0:
                body_color = (80, 80, 80)
            else:
                body_color = (40, 40, 40)
        elif self.color_override:
            body_color = self.color_override
        else:
            body_color = (40, 40, 50) # Normal

        dx = self.x + shake_x
        dy = self.y

        if self.red_tint:
            body_color = (max(body_color[0], 80), body_color[1], body_color[2])

        if self.image:
            #Create a copy to not permanently dye the original image
            boss_surf = self.image.copy()

            if self.hit_timer > 0:
                #Flash White/Red when hit
                boss_surf.fill((100, 50, 50), special_flags=pygame.BLEND_RGB_ADD)
            elif self.color_override == WHITE:
                # White Flash (Phase transition)
                boss_surf.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
            elif self.has_gone_berserk:
                #Berserk Mode: Tint it Red (Multiply) using the flickering body_color
                boss_surf.fill(body_color, special_flags=pygame.BLEND_RGBA_MULT)
            elif self.state == "STUNNED":
                #Stunned: Darken/Grey out
                boss_surf.fill((100, 100, 100), special_flags=pygame.BLEND_RGBA_MULT)
            elif self.red_tint:
                #Phase 4 Tint: Slight Red Multiply
                boss_surf.fill((255, 200, 200), special_flags=pygame.BLEND_RGBA_MULT)

            #ALIGNMENT FIX
            img_rect = boss_surf.get_rect(center=(int(dx + 150), int(dy + 350)))
            screen.blit(boss_surf, img_rect)

            #Outline uses the image size
            outline_rect = img_rect.inflate(100, 30)
            alpha = 0 

            outline_surf = pygame.Surface((outline_rect.width, outline_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(
                outline_surf,
                (*LIGHT_GRAY, alpha),
                outline_surf.get_rect(),
                6
            )
            screen.blit(outline_surf, outline_rect.topleft)


        else:
            #Draw the 4 Parts
            pygame.draw.rect(screen, body_color, (dx, dy - 400, 200, 1500)) 
            pygame.draw.rect(screen, LIGHT_GRAY, (dx, dy - 400, 200, 1500), 5)
            
            #Protruding Parts (Engines and Cockpit)
            pygame.draw.rect(screen, (60, 60, 70), (dx - 150, dy + 50, 180, 120)) #Top Eng
            pygame.draw.rect(screen, RED, (dx - 150, dy + 60, 180, 100), 2)
            
            pygame.draw.rect(screen, (60, 60, 70), (dx - 150, dy + 530, 180, 120)) #Bot Eng
            pygame.draw.rect(screen, RED, (dx - 150, dy + 540, 180, 100), 2)
            
            pygame.draw.rect(screen, (80, 80, 100), (dx - 80, dy + 275, 100, 150)) #Cockpit
            pygame.draw.rect(screen, BLUE, (dx - 60, dy + 300, 40, 100))

        if self.coil: self.coil.draw(screen)

        #BUBBLE SHIELD
        if self.shield_active:
            s = pygame.Surface((800, 800), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 150, 255, 40), (400, 400), 380)
            pygame.draw.circle(s, (150, 220, 255, 100), (400, 400), 380, 8)
            screen.blit(s, (self.x - 400, self.y - 50))

        #White Flash Overlay
        if self.white_flash > 0:
            flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            flash_surf.fill(WHITE)
            flash_surf.set_alpha(self.white_flash)
            screen.blit(flash_surf, (0, 0))
            self.white_flash -= 5

        #MEGA LASER BUILDUP RINGS
        if self.state == "CHARGING" and self.current_attack == "MEGA_LASER":
            for i in range(1, 4):
                ring_rad = ((pygame.time.get_ticks() // 5) + (i * 20)) % 60
                pygame.draw.circle(screen, (0, 255, 255), (int(dx - 80), int(dy + 350)), int(ring_rad), 2)

        #DEATH BEAM VISUALS
        if self.state == "DYING_WINDUP":
            # arning Zone (Center)
            warn_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - 300), pygame.SRCALPHA)
            warn_surf.fill((255, 0, 0, 50))
            screen.blit(warn_surf, (0, 150))
            #Warning Lines
            pygame.draw.line(screen, RED, (0, 150), (SCREEN_WIDTH, 150), 5)
            pygame.draw.line(screen, RED, (0, SCREEN_HEIGHT - 150), (SCREEN_WIDTH, SCREEN_HEIGHT - 150), 5)
            txt = font.render("!!! FINAL DISCHARGE !!!", True, RED)
            screen.blit(txt, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2))

        if self.state == "DYING_LASER":
            #The Beam
            pygame.draw.rect(screen, (255, 200, 200), (0, 150, SCREEN_WIDTH, SCREEN_HEIGHT - 300))
            pygame.draw.rect(screen, WHITE, (0, 150, SCREEN_WIDTH, SCREEN_HEIGHT - 300), 20)

        #VISUAL CUE FOR STUN
        if self.state == "STUNNED":
            stun_txt = font.render("SYSTEM FAILURE - VULNERABLE", True, RED)
            screen.blit(stun_txt, (dx - 200, dy + 350))

        #BOSS UI (Bottom)
        bar_w = 600
        bar_x = SCREEN_WIDTH // 2 - 300
        bar_y = SCREEN_HEIGHT - 40 
        pygame.draw.rect(screen, DARK_GRAY, (bar_x, bar_y, bar_w, 20))
        display_ratio = self.bar_fill if self.is_entering else (self.hp / self.max_hp)
        pygame.draw.rect(screen, RED, (bar_x, bar_y, int(bar_w * display_ratio), 20))
        pygame.draw.rect(screen, WHITE, (bar_x, bar_y, bar_w, 20), 2)

        name_txt = font.render("GOLIATH MOTHERBOARD", True, WHITE)
        name_rect = name_txt.get_rect(centerx=SCREEN_WIDTH//2, bottom=bar_y - 5)
        screen.blit(name_txt, name_rect)
        
        #PHASE MARKERS (66%, 33%, 10%)
        for pct in [0.66, 0.33, 0.1]:
            marker_x = bar_x + int(bar_w * pct)
            pygame.draw.line(screen, WHITE, (marker_x, bar_y), (marker_x, bar_y + 20), 3)

        if self.state == "MEGA_LASER_FIRE":
            #~3x Thicker than officer
            lx = self.shoot_origin_x
            pygame.draw.line(screen, (0, 255, 255), (lx, self.y + 350), (0, self.y + 350), 45)
            pygame.draw.line(screen, WHITE, (lx, self.y + 350), (0, self.y + 350), 15)

        #Draw Death FX
        for fx in self.death_fx:
            fx.draw(screen)

    def get_hitboxes(self):
        base = pygame.Rect(self.x, self.y - 400, 200, 1500) 
        top_eng = pygame.Rect(self.x - 150, self.y + 50, 180, 120)
        bot_eng = pygame.Rect(self.x - 150, self.y + 530, 180, 120)
        cockpit = pygame.Rect(self.x - 80, self.y + 275, 100, 150)
        return [base, top_eng, bot_eng, cockpit]


class Coil:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = 5
        self.hit_flash = 0
        self.rect = pygame.Rect(x-40, y-40, 80, 80)

    def draw(self, screen):
        #Draw the Coil itself
        color = (255, 100, 100) if self.hit_flash > 0 else (200, 200, 0)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), 40)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), 15, 2)
        if self.hit_flash > 0: self.hit_flash -= 1

        #5 HP BARS (Fills as it gets damaged)
        damage_taken = 5 - self.hp
        bar_start_x = self.x - 50
        for i in range(5):
            segment_color = RED if i < self.hp else (60, 60, 60)
            pygame.draw.rect(screen, segment_color, (bar_start_x + (i * 22), self.y - 70, 18, 8))
            pygame.draw.rect(screen, WHITE, (bar_start_x + (i * 22), self.y - 70, 18, 8), 1)


class Game:

    def reset_game_logic_only(self):
        self.enemies.clear()
        self.bullets.clear()
        self.officers.clear()
        self.wave_2_banzai_total = 0
        self.scare_officers_spawned = False
        if hasattr(self, 'scare_step'):
            self.scare_step = 0
            self.spawn_idx = 0

    def reset_game(self):
        self.player = PlayerJet(self.player_image)
        self.enemies.clear()
        self.bullets.clear()
        self.particles.clear()
        self.pickups.clear()
        self.officers.clear()
        

        self.boss = None            
        self.wave = 1               
        self.officer_phase = 0     
        self.wave_progress = 0     
        self.scare_officers_spawned = False 
        self.scare_step = 0
        self.spawn_idx = 0
        self.boss_defeated = False

        self.kills = 0        

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Fighter Jet Dogfight")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = GameState.MENU

        # Load assets with fallbacks
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ASSET_DIR = os.path.join(base_dir, "asset")

        def get_image(filename, w, h, fallback_color=WHITE, is_triangle=False):
            path = os.path.join(ASSET_DIR, filename)
            try:
                img = pygame.image.load(path).convert_alpha()
                return pygame.transform.scale(img, (w, h))
            except Exception as e:
                print(f"FAILED to load {path}, using shape. Error: {e}")
                surf = pygame.Surface((w, h), pygame.SRCALPHA)
                if is_triangle:
                    pygame.draw.polygon(surf, fallback_color, [(w, h//2), (0, 0), (0, h)])
                else:
                    pygame.draw.rect(surf, fallback_color, (0, 0, w, h))
                    pygame.draw.rect(surf, (255, 255, 255), (0, 0, w, h), 2)
                return surf

        self.player_image = get_image("jet1.png", 60, 40, WHITE, True)

        self.enemy_image = get_image("jet2.png", 55, 35, RED, True)

        self.officer_image = get_image("officer.png", 60, 60, BLUE, False)

        self.boss_image = get_image("boss.png", 200, 1500, (50, 50, 50), False)

        try:
            self.menu_bg = pygame.image.load(os.path.join(ASSET_DIR, "mainmenubg.jpg")).convert()
            self.menu_bg = pygame.transform.scale(self.menu_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except: 
            self.menu_bg = None

        try:
            self.game_bg = pygame.image.load(os.path.join(ASSET_DIR, "galaxybg.png")).convert()
            self.game_bg = pygame.transform.scale(self.game_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except: 
            self.game_bg = None

        self.player = PlayerJet(self.player_image)
        self.enemies: List[EnemyJet] = []
        self.bullets: List[Bullet] = []
        self.particles: List[Particle] = []
        self.pickups: List[Pickup] = []

        self.kills = 0
        self.wave = 1
        self.last_enemy_spawn = 0
        self.last_pickup_spawn = 0
        self.screen_shake_intensity = 0

        self.start_time = 0
        self.elapsed_time = 0
        self.wave_transition_timer = 0
        self.shockwave_radius = 0
        self.wave_2_banzai_total = 0

        self.wave_progress = 0
        self.total_kills = 0

        self.officers = []
        self.officer_phase = 0 
        self.officer_spawn_timer = 0

        self.boss = None
        self.boss_defeated = False
        self.scare_timer = 0
        self.scare_officers_spawned = False

        self.victory_timer = 0
        self.fade_alpha = 0

        self.box_slots = 0
        self.box_cooldown_timer = 0

        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)

        #MOBILE CONTROLS
        self.joystick = VirtualJoystick(100, SCREEN_HEIGHT - 100)

        self.btn_shoot = MobileButton(
            SCREEN_WIDTH - 180, SCREEN_HEIGHT - 100, BUTTON_SIZE, "Fire"
        )

        self.btn_dash = MobileButton(
            SCREEN_WIDTH - 270, SCREEN_HEIGHT - 170, BUTTON_SIZE, "Dash"
        )
        self.btn_dash.cooldown = DASH_COOLDOWN

        self.btn_grenade = MobileButton(
            SCREEN_WIDTH - 180, SCREEN_HEIGHT - 240, BUTTON_SIZE, "Bomb"
        )
        self.play_btn = pygame.Rect(SCREEN_WIDTH//2 - 120, 350, 240, 60)
        self.quit_btn = pygame.Rect(SCREEN_WIDTH//2 - 120, 430, 240, 60)


    def reset_game(self):
        self.player = PlayerJet(self.player_image)
        self.enemies.clear()
        self.bullets.clear()
        self.particles.clear()
        self.pickups.clear()
        self.officers.clear()

        self.kills = 0            
        self.total_kills = 0
        self.wave_progress = 0     
        self.wave = 1
        self.officer_phase = 0
        self.wave_2_banzai_total = 0

        if self.boss:
            del self.boss
        self.boss = None
        self.scare_officers_spawned = False
        self.scare_step = 0
        
        self.start_time = pygame.time.get_ticks() 
        self.elapsed_time = 0
        self.last_enemy_spawn = pygame.time.get_ticks()
        self.last_pickup_spawn = pygame.time.get_ticks()
        self.screen_shake_intensity = 0

    def get_wave_params(self):
        max_enemies = ENEMY_MAX_ACTIVE + (self.wave - 1) * 2 
        #Spawns much faster in higher waves
        spawn_delay = max(300, ENEMY_SPAWN_DELAY - (self.wave - 1) * 400)
        return max_enemies, spawn_delay

    def spawn_enemy(self):
        y = random.randint(50, SCREEN_HEIGHT - 50)
        x = SCREEN_WIDTH + 50
        is_banzai = False
        
        if self.wave == 2:
            #Force exactly 5 banzais spread across wave 2 progress
            needed_banzais = (self.wave_progress - WAVE_1_TARGET) // 3
            if self.wave_2_banzai_total < 5 and self.wave_2_banzai_total <= needed_banzais:
                is_banzai = True
                self.wave_2_banzai_total += 1
        elif self.wave == 3:
            if random.random() < 0.5: #50% Banzai chaos in Wave 3
                is_banzai = True
        elif self.wave >= 4:
            if random.random() < 0.25:
                is_banzai = True
                
        self.enemies.append(EnemyJet(x, y, self.wave, self.enemy_image, is_banzai))
        

    def spawn_pickup(self):
        x = random.randint(80, SCREEN_WIDTH - 80)
        y = random.randint(80, SCREEN_HEIGHT - 80)
        self.pickups.append(Pickup(x, y))

    def create_explosion(self, x: float, y: float, color: Tuple[int, int, int]):
        for _ in range(12):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 6)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            self.particles.append(Particle(x, y, vx, vy, color))

    def screen_shake(self, intensity: int):
        self.screen_shake_intensity = max(self.screen_shake_intensity, intensity)

    def trigger_directional_dash(self, current_time):
        keys = pygame.key.get_pressed()
        k_dx, k_dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: k_dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: k_dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: k_dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: k_dx += 1

        joy_vec = self.joystick.vector
        
        if k_dx != 0 or k_dy != 0:
            mag = math.sqrt(k_dx**2 + k_dy**2)
            dash_dir = (k_dx/mag, k_dy/mag)
        elif joy_vec.length() > 0.1:
            dash_dir = (joy_vec.x, joy_vec.y)
        else:
            rad = math.radians(self.player.angle)
            dash_dir = (math.cos(rad), math.sin(rad))
            
        if current_time - self.player.last_dash_time > DASH_COOLDOWN:
            self.player.is_dashing = True
            self.player.dash_start_time = current_time
            self.player.last_dash_time = current_time
            self.player.dash_direction = dash_dir
            self.btn_dash.last_used = current_time

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            self.joystick.handle(event)

            #MOUSE / TOUCH CONTROLS
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.state == GameState.MENU:
                    if self.play_btn.collidepoint(event.pos):
                        self.reset_game()
                        self.state = GameState.PLAYING
                    elif self.quit_btn.collidepoint(event.pos):
                        self.running = False

                elif self.state == GameState.PLAYING:
                    now = pygame.time.get_ticks()

                    if self.btn_shoot.rect.collidepoint(event.pos):
                        bullet = self.player.shoot(now)
                        if bullet:
                            self.bullets.append(bullet)

                    if self.btn_dash.rect.collidepoint(event.pos) and self.btn_dash.ready():
                        self.trigger_directional_dash(now)
                        self.btn_dash.last_used = now

                    if self.btn_grenade.rect.collidepoint(event.pos):
                        grenade = self.player.fire_grenade(now)
                        if grenade:
                            self.bullets.append(grenade)

            #KEYBOARD CONTROLS
            if event.type == pygame.KEYDOWN:
                #Cheat Codes (P + Number)
                keys = pygame.key.get_pressed()
                if keys[pygame.K_p]:
                    if event.key == pygame.K_1: 
                        self.kills = 0; self.wave_progress = 0; self.wave = 1
                    if event.key == pygame.K_2: 
                        self.kills = WAVE_1_TARGET; self.wave_progress = WAVE_1_TARGET; self.wave = 2
                    if event.key == pygame.K_3: 
                        self.kills = WAVE_2_TARGET; self.wave_progress = WAVE_2_TARGET; self.wave = 3
                    if event.key == pygame.K_4: 
                        self.kills = WAVE_3_TARGET; self.wave_progress = WAVE_3_TARGET; self.wave = 4
                        self.officer_phase = 1
                    if event.key == pygame.K_5:
                        self.kills = WAVE_3_TARGET; self.wave_progress = WAVE_3_TARGET; self.wave = 4
                        self.officer_phase = 3; self.officers.clear(); self.boss = None
                        self.scare_step = 0; self.spawn_idx = 0; self.scare_timer = pygame.time.get_ticks()
                    if event.key == pygame.K_6:
                        self.kills = WAVE_3_TARGET; self.wave_progress = WAVE_3_TARGET; self.wave = 5
                        self.officer_phase = 4; self.officers.clear(); self.boss = Boss()
                        if self.boss and self.boss_image:
                            self.boss.image = self.boss_image
                    if event.key == pygame.K_7 and self.boss:
                        self.boss.hp = self.boss.max_hp * 0.67
                        self.boss.current_phase = 1 
                        self.boss.is_entering = False 
                        self.boss.bar_fill = 1.0
                    if event.key == pygame.K_8 and self.boss:
                        self.boss.hp = self.boss.max_hp * 0.34
                        self.boss.current_phase = 2 
                        self.boss.is_entering = False
                        self.boss.bar_fill = 1.0
                    if event.key == pygame.K_9 and self.boss:
                        self.boss.hp = self.boss.max_hp * 0.11
                        self.boss.is_entering = False
                        self.boss.bar_fill = 1.0
                    if event.key == pygame.K_0: 
                        self.player.invincible_cheat = not self.player.invincible_cheat
                    
                    self.player.hp = 100
                    self.reset_game_logic_only()

                if self.state == GameState.MENU:
                    if event.key == pygame.K_RETURN:
                        self.state = GameState.PLAYING
                        self.reset_game()
                elif self.state == GameState.GAME_OVER:
                    if event.key == pygame.K_r:
                        self.state = GameState.PLAYING
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                elif self.state == GameState.PLAYING:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False


    def update_playing(self):
        current_time = pygame.time.get_ticks()
        
        #SHIELD COLLISION (Bullet & Player block)
        if self.boss and self.boss.shield_active:
            shield_rect = pygame.Rect(self.boss.x - 400, self.boss.y - 50, 800, 800)

            #POSITION OFFICERS
            for i, off in enumerate(self.officers):
                off.role = "guard"
                off.role_index = i
                
                if self.boss.coil:
                    if not off.is_firing:
                        target_y = self.player.y if i == 0 else self.player.y + 200
                        off.y += (target_y - off.y) * 0.05

            #Block Bullets
            for b in self.bullets[:]:
                if b.is_player and shield_rect.collidepoint(b.x, b.y):
                    b.active = False
            #Block Player
            p_rect = self.player.get_rect()
            if p_rect.colliderect(shield_rect):
                self.player.x = shield_rect.left - self.player.width 

        #LASER VS COIL DETECTION
            if self.boss.coil:
                for off in self.officers:
                    if off.is_firing:
                        if abs(off.y - self.boss.coil.y) < 40:
                            if not hasattr(off, 'has_hit_coil'):
                                self.boss.coil.hp -= 1
                                self.boss.coil.hit_flash = 10
                                off.has_hit_coil = True
                                self.screen_shake(15)
                    else:
                        if hasattr(off, 'has_hit_coil'): del off.has_hit_coil

            if self.boss.coil.hp <= 0:

                self.boss.coil = None
                self.boss.shield_active = False
                self.boss.white_flash = 255
                self.screen_shake(50)
                self.boss.state = "IDLE"

        if self.player.hp <= 0:
            if self.player.lives > 0:
                self.player.lives -= 1
                self.player.hp = 100
                self.player.invincible_timer = current_time + 3000
            else:
                self.state = GameState.GAME_OVER

        #HP Regen Logic
        if self.player.regen_end_time > current_time:
            self.player.hp = min(100, self.player.hp + 0.2) 

        #Timer Setup
        if self.start_time == 0: self.start_time = current_time
        self.elapsed_time = (current_time - self.start_time) // 1000

        # Input Handling
        keys = pygame.key.get_pressed()

        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1

        if dx != 0 and dy != 0:
            length = math.sqrt(dx * dx + dy * dy)
            dx /= length
            dy /= length

        self.player.move(dx, dy, current_time, keys[pygame.K_LSHIFT], self.joystick.vector)

        if self.player.is_dashing:
            self.btn_dash.last_used = self.player.last_dash_time

        if keys[pygame.K_SPACE]:
            bullet = self.player.shoot(current_time)
            if bullet:
                self.bullets.append(bullet)

        if keys[pygame.K_f]:
            grenade = self.player.fire_grenade(current_time)
            if grenade:
                self.bullets.append(grenade)

        if len(self.pickups) < MAX_PICKUPS and (current_time - self.last_pickup_spawn) >= PICKUP_SPAWN_DELAY:
            self.spawn_pickup()
            self.last_pickup_spawn = current_time

        for pu in self.pickups[:]:
            if pu.is_expired(current_time):
                self.pickups.remove(pu)

        max_enemies, spawn_delay = self.get_wave_params()
         # Reduce spawn rate if Officer is active
        spawn_mod = 0.2 if self.officers else 1.0
        if len(self.enemies) < (max_enemies * spawn_mod):
            if current_time - self.last_enemy_spawn >= (spawn_delay / spawn_mod):
                if self.officer_phase < 3: 
                    self.spawn_enemy()
                    self.last_enemy_spawn = current_time

        #Update enemies
        for enemy in self.enemies[:]:
            status = enemy.update(self.player.x, self.player.y)
            
            if status == "escaped":
                #KILLS (Score) is penalized, but Wave Progress is NOT affected
                self.kills = max(0, self.kills - 50) 
                self.enemies.remove(enemy)
                continue

            if not enemy.is_banzai:
                bullet = enemy.try_shoot(current_time, self.player.x, self.player.y)
                if bullet: self.bullets.append(bullet)

            if not enemy.active:
                            self.kills += 1           
                            self.wave_progress += 1   
                            self.create_explosion(enemy.x, enemy.y, ORANGE)
                            if enemy in self.enemies:
                                self.enemies.remove(enemy)


        #WAVE TRANSITION LOGIC
        target_wave = 1
        if self.wave_progress >= WAVE_3_TARGET: 
            target_wave = 4 
            if self.officer_phase == 0:
                self.officer_phase = 1
        elif self.wave_progress >= WAVE_2_TARGET: target_wave = 3
        elif self.wave_progress >= WAVE_1_TARGET: target_wave = 2

        if target_wave > self.wave:
            self.wave = target_wave
            self.wave_transition_timer = current_time + 4000
            self.screen_shake(40)
            #If we just hit Wave 4, start Phase 1
            if self.wave == 4: 
                self.officer_phase = 1 
            
        #OFFICER SPAWNING LOGIC (Force Phase 1 if in Wave 4)
        if self.wave >= 4 and not self.boss:
            if self.officer_phase == 0: self.officer_phase = 1
            
            #check ALL combat roles. If only 1 is left, they MUST become Main.
            combat_officers = [o for o in self.officers if o.role in ["main", "sub", "sub_top", "sub_bot"]]
            if len(combat_officers) == 1:
                combat_officers[0].role = "main"

            #PHASE 1: SPAWN MAIN OFFICER
            if self.officer_phase == 1 and not self.officers:
                off = Officer(SCREEN_WIDTH + 100, SCREEN_HEIGHT//2, self.officer_image, "main")
                off.role_index = 0
                self.officers.append(off)
            
            #PHASE 2: SPAWN 2 OFFICERS
            elif self.officer_phase == 2 and not self.officers and current_time > self.officer_spawn_timer:
                #Spawn MAIN (Targets Player directly)
                off1 = Officer(SCREEN_WIDTH + 100, 200, self.officer_image, "main")
                off1.role_index = 0
                #Spawn SUB (Targets below Player)
                off2 = Officer(SCREEN_WIDTH + 100, 500, self.officer_image, "sub_bot")
                off2.role_index = 1
                self.officers.extend([off1, off2])
            
            #PHASE 3: THE SCARE MOVIE
            elif self.officer_phase == 3:
                if not hasattr(self, 'scare_step') or self.scare_step > 7: 
                    self.scare_step = 0; self.spawn_idx = 0; self.scare_timer = current_time
                
                #Spawn 5 Officers one by one
                if self.scare_step == 0:
                    if self.spawn_idx < 5:
                        if current_time - self.scare_timer > 800:
                            wedge = [(800, 350), (880, 250), (880, 450), (950, 150), (950, 550)]
                            off = Officer(SCREEN_WIDTH + 50, random.randint(0, 700), self.officer_image, "scare")
                            off.target_pos = wedge[self.spawn_idx]
                            self.officers.append(off)
                            self.spawn_idx += 1
                            self.scare_timer = current_time
                    else:
                        all_ready = all(abs(o.x - o.target_pos[0]) < 10 for o in self.officers)
                        if all_ready:
                            self.scare_step = 1
                            self.scare_timer = current_time + 1000

                #Wind Up
                elif self.scare_step == 1:
                    if current_time > self.scare_timer:
                        for off in self.officers: off.state = "winding"
                        self.scare_step = 2
                        self.scare_timer = current_time + 1000

                #FIRE LASERS
                elif self.scare_step == 2:
                    if current_time > self.scare_timer:
                        for off in self.officers: off.is_firing = True
                        self.scare_step = 3
                        self.scare_timer = current_time + 2000

                #Stop Fire & Hover
                elif self.scare_step == 3:
                    if current_time > self.scare_timer:
                        for off in self.officers: 
                            off.is_firing = False
                            off.state = "hover"
                        self.scare_step = 4
                        self.scare_timer = current_time + 2000

                #Exclamation Flicker
                elif self.scare_step == 4:
                    if current_time > self.scare_timer:
                        for off in self.officers: off.show_alert = "flicker"
                        self.scare_step = 5
                        self.scare_timer = current_time + 1000

                #Exclamation Solid
                elif self.scare_step == 5:
                    if current_time > self.scare_timer:
                        for off in self.officers: off.show_alert = "solid"
                        self.scare_step = 6
                        self.scare_timer = current_time + 1000

                #Remove Alert & Prepare Launch
                elif self.scare_step == 6:
                    if current_time > self.scare_timer:
                        for off in self.officers: del off.show_alert
                        self.scare_step = 7
                        self.scare_timer = current_time
                        self.exit_idx = 0

                #Rocket Away One by One
                elif self.scare_step == 7:
                    if self.exit_idx < len(self.officers):
                        if current_time - self.scare_timer > 300: 
                            self.officers[self.exit_idx].role = "rocket"
                            self.exit_idx += 1
                            self.scare_timer = current_time
                    else:
                        if all(o.x > SCREEN_WIDTH for o in self.officers):
                            self.officers.clear() 
                            
                            if not self.boss:
                                self.boss = Boss()
                                if self.boss_image:
                                    self.boss.image = self.boss_image
                                self.boss.x = SCREEN_WIDTH + 100
                                self.wave = 5 
                                self.officer_phase = 4

        combatants = [o for o in self.officers if o.role in ["main", "sub", "sub_top", "sub_bot", "guard"]]
        if len(combatants) == 1:
            survivor = combatants[0]
            if not self.boss:
                survivor.role = "main"
            elif self.boss and survivor.role == "guard":
                survivor.role_index = 0

        for off in self.officers:
            off.update(self.player.x, self.player.y, self)
            if off.check_laser_hit(self.player.get_rect()):
                if self.player.invincible_timer < current_time and not self.player.invincible_cheat:
                    self.player.take_damage(OFFICER_LASER_DAMAGE)
                    
                    if self.player.hp <= 0:
                        if self.player.lives > 0:
                            self.player.lives -= 1
                            self.player.hp = PLAYER_MAX_HP
                            self.player.invincible_timer = current_time + INVINCIBLE_TIME
                        else:
                            self.state = GameState.GAME_OVER
                            self.create_explosion(self.player.x, self.player.y, RED)
        if self.boss:
            self.boss.update(self.player.x, self.player.y, self) 
            

        for bullet in self.bullets:
            bullet.update()

        for i in range(len(self.bullets)):
            b1 = self.bullets[i]
            if not b1.active:
                continue
            for j in range(i + 1, len(self.bullets)):
                b2 = self.bullets[j]
                if not b2.active:
                    continue
                if b1.is_player == b2.is_player:
                    continue
                if b1.get_rect().colliderect(b2.get_rect()):
                    mx = (b1.x + b2.x) / 2
                    my = (b1.y + b2.y) / 2
                    self.create_explosion(mx, my, YELLOW)
                    b1.active = False
                    b2.active = False
                    self.screen_shake(4)

        self.bullets = [b for b in self.bullets if b.active]

        for bullet in self.bullets[:]:
            if not bullet.is_player or not bullet.active:
                continue

            bullet_rect = bullet.get_rect()

            dmg_amount = PLAYER_GRENADE_DAMAGE if bullet.is_grenade else PLAYER_BULLET_DAMAGE
            
            #Standard Enemies & Banzais
            for enemy in self.enemies[:]:
                if bullet_rect.colliderect(enemy.get_rect()):
                    enemy.take_damage(dmg_amount) 
                    bullet.active = False
                    if not enemy.active:
                        self.kills += (250 if enemy.is_banzai else 100)
                        self.total_kills += 1
                        self.wave_progress += 1
                        self.create_explosion(enemy.x, enemy.y, ORANGE)
                        self.enemies.remove(enemy)
                    break 
            
            #Officers
            if bullet.active:
                for off in self.officers[:]:
                    if bullet_rect.colliderect(off.get_rect()):
                        off.take_damage(PLAYER_BULLET_DAMAGE)
                        bullet.active = False
                        if off.hp <= 0:
                            self.kills += 5000       
                            self.total_kills += 1     
                            self.wave_progress += 5   
                            self.create_explosion(off.x, off.y, BLUE)
                            self.officers.remove(off)
                            if off.role == "guard" and self.boss:
                                self.boss.officer_respawn_timer = current_time + 7000
                            if not self.officers:
                                if self.officer_phase == 1:
                                    self.officer_phase = 2
                                    self.officer_spawn_timer = current_time + 2000
                                elif self.officer_phase == 2:
                                    self.officer_phase = 3
                                    self.wave = 5 
                                    self.scare_step = 0 
                                    self.spawn_idx = 0
                                    self.scare_timer = current_time
                        break
                    if bullet.active and self.boss and not self.boss.is_entering: 
                        for hitbox in self.boss.get_hitboxes():
                            if bullet_rect.colliderect(hitbox):
                             self.boss.hp -= PLAYER_BULLET_DAMAGE
                             bullet.active = False
                             self.create_explosion(bullet.x, bullet.y, YELLOW)
                             self.kills += 10
                             break

        self.bullets = [b for b in self.bullets if b.active]

        #ENEMY BULLET LOGIC (Tracking + Damage)
        for bullet in self.bullets:
            if bullet.is_player or not bullet.active: 
                continue
            
            #BANZAI MISSILE LOGIC
            if bullet.width == 16:
                if bullet.x > 600:
                    if hasattr(bullet, 'target_row_y'):
                        bullet.y += (bullet.target_row_y - bullet.y) * 0.1
                        bullet.vx = -6 
                #Home to player
                elif bullet.x > self.player.x + 20:
                    dx = self.player.x - bullet.x
                    dy = self.player.y - bullet.y
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        bullet.vx = (dx/dist) * 4 
                        bullet.vy = (dy/dist) * 4
                #Passed (Locked path)
                else:
                    pass 

            #HIT DETECTION (Enemy Bullet hitting Player)
            if bullet.get_rect().colliderect(self.player.get_rect()):
                if self.player.invincible_timer < current_time and not self.player.invincible_cheat:
                    damage = ENEMY_BULLET_DAMAGE_BASE + (self.wave - 1) * 2
                    self.player.take_damage(damage)
                    bullet.active = False
                    self.screen_shake(10)
                    self.create_explosion(bullet.x, bullet.y, RED)
                    
                    #DEATH LOGIC
                    if self.player.hp <= 0:
                        if self.player.lives > 0:
                            self.player.lives -= 1
                            self.player.hp = 100
                            self.player.invincible_timer = current_time + 3000
                        else:
                            self.state = GameState.GAME_OVER
                else:
                    bullet.active = False

        for bullet in self.bullets[:]:
            if not bullet.is_player or not bullet.active:
                continue

            bullet_rect = bullet.get_rect()
            
            dmg_amount = PLAYER_GRENADE_DAMAGE if bullet.is_grenade else PLAYER_BULLET_DAMAGE

            #Standard Enemies
            for enemy in self.enemies[:]:
                if bullet_rect.colliderect(enemy.get_rect()):
                    enemy.take_damage(dmg_amount) 
                    bullet.active = False
                    if not enemy.active:
                        self.kills += 100         
                        self.total_kills += 1     
                        self.wave_progress += 1   
                        self.create_explosion(enemy.x, enemy.y, ORANGE)
                        if enemy in self.enemies: self.enemies.remove(enemy)
                    break 
            
            if not bullet.active: continue

            #Officer Check
            for off in self.officers[:]:
                if bullet_rect.colliderect(off.get_rect()):
                    off.take_damage(PLAYER_BULLET_DAMAGE)
                    bullet.active = False
                    if off.hp <= 0:
                        self.kills += 5000; self.total_kills += 1; self.wave_progress += 5
                        self.create_explosion(off.x, off.y, BLUE)
                        
                        if off.role == "guard" and self.boss:
                            self.boss.officer_respawn_timer = current_time + 7000
                        
                        if off in self.officers: self.officers.remove(off)
                        
                        if not self.officers:
                            if self.officer_phase == 1:
                                self.officer_phase = 2; self.officer_spawn_timer = current_time + 2000
                            elif self.officer_phase == 2:
                                self.officer_phase = 3; self.wave = 5
                                self.scare_step = 0; self.spawn_idx = 0; self.scare_timer = current_time
                    break
            
            if not bullet.active: continue

            #BOSS CHECK
            if self.boss and not self.boss.is_entering and bullet.is_player:
                for hitbox in self.boss.get_hitboxes():
                    if bullet_rect.colliderect(hitbox):
                        #IGNORE BULLETS IF SEQUENCE STARTED
                        if self.boss.state in ["DYING_STILL", "DYING_WINDUP", "DYING_LASER", "FALLING"]:
                            bullet.active = False; break

                        #APPLY DAMAGE
                        dmg = PLAYER_GRENADE_DAMAGE if bullet.is_grenade else PLAYER_BULLET_DAMAGE
                        actual_dmg = dmg * (1.0 - self.boss.damage_reduction)
                        self.boss.hp -= actual_dmg
                        self.boss.hit_timer = 5 
                        bullet.active = False
                        self.create_explosion(bullet.x, bullet.y, YELLOW)

                        #CHECK TRIGGERS
                        if self.boss.has_gone_berserk and self.boss.hp <= (self.boss.max_hp * 0.02):
                            self.boss.hp = 1
                            self.boss.state = "DYING_STILL"
                            self.boss.state_timer = current_time + 1000
                            self.boss.damage_reduction = 1.0
                            self.enemies.clear()
                        
                        #Safety Clamp
                        if self.boss.hp <= 0: self.boss.hp = 1
                        
                        break

        self.bullets = [b for b in self.bullets if b.active]

        # PLAYER HIT BY ENEMY BULLETS
        for bullet in self.bullets:
            if bullet.is_player or not bullet.active: continue
            
            #KAMIKAZE DORITO LOGIC
            if bullet.width == 16:
                #Vertical Spreading (Right half of screen)
                if bullet.x > 500:
                    if hasattr(bullet, 'target_row_y'):
                        bullet.y += (bullet.target_row_y - bullet.y) * 0.1
                        bullet.vx = -7 
                #Home to player (But 50% slower)
                elif bullet.x > self.player.x + 20:
                    dx = self.player.x - bullet.x
                    dy = self.player.y - bullet.y
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        bullet.vx = (dx/dist) * 4 
                        bullet.vy = (dy/dist) * 4

                else:
                    pass

            #HIT DETECTION
            if bullet.get_rect().colliderect(self.player.get_rect()):
                if self.player.invincible_timer < current_time and not self.player.invincible_cheat:
                    self.player.take_damage(10)
                    bullet.active = False
                    self.create_explosion(bullet.x, bullet.y, RED)
                    if self.player.hp <= 0:
                        if self.player.lives > 0:
                            self.player.lives -= 1; self.player.hp = 100
                            self.player.invincible_timer = current_time + 3000
                        else: self.state = GameState.GAME_OVER
                else: bullet.active = False

        player_rect = self.player.get_rect()
        for enemy in self.enemies[:]:
            if player_rect.colliderect(enemy.get_rect()):
                self.player.grenades = self.player.max_grenades


                if self.player.invincible_timer < current_time and not self.player.invincible_cheat:
                    self.player.take_damage(ENEMY_COLLISION_DAMAGE)
                    self.screen_shake(15)
                    if self.player.hp <= 0:
                        if self.player.lives > 0:
                            self.player.lives -= 1
                            self.player.hp = PLAYER_MAX_HP
                            self.player.invincible_timer = current_time + INVINCIBLE_TIME
                        else:
                            self.state = GameState.GAME_OVER
                            self.create_explosion(self.player.x, self.player.y, RED)
                
                enemy.active = False
                if enemy in self.enemies:
                    self.enemies.remove(enemy)
                self.create_explosion(enemy.x, enemy.y, ORANGE)

            #BOSS RAMMING
        if self.boss and not self.boss.is_entering:
            p_rect = self.player.get_rect()
            for hitbox in self.boss.get_hitboxes():
                if p_rect.colliderect(hitbox):
                    if self.player.invincible_timer < current_time and not self.player.invincible_cheat:
                        self.player.take_damage(50)
                        self.screen_shake(30)
                        # Bounce player back
                        self.player.x -= 100 

        #OFFICER COLLISION
        for off in self.officers:
            if self.player.get_rect().colliderect(off.get_rect()):
                if self.player.invincible_timer < current_time and not self.player.invincible_cheat:
                    self.player.take_damage(20)
                    self.screen_shake(10)
                    if self.player.hp <= 0:
                        if self.player.lives > 0:
                            self.player.lives -= 1
                            self.player.hp = 100
                            self.player.invincible_timer = current_time + 3000
                        else: 
                            self.state = GameState.GAME_OVER

        for pu in self.pickups[:]:
            px, py = pu.x, pu.y
            player_center = Position(self.player.x, self.player.y)
            dist = math.hypot(player_center.x - px, player_center.y - py)
            collect_threshold = pu.radius + max(self.player.width, self.player.height) / 2
            
            if dist <= collect_threshold:
                now = pygame.time.get_ticks()
                
                #Logic for BOX SLOTS (+1 Life progress), If HP is 100 and Grenades are full, fill a slot
                if self.player.hp >= 100 and self.player.grenades >= self.player.max_grenades:
                    if now > self.box_cooldown_timer:
                        self.box_slots += 1
                        if self.box_slots >= 3:
                            self.player.lives += 1
                            self.box_slots = 0
                            self.box_cooldown_timer = now + BOX_COOLDOWN_TIME
                
                #Logic for HP REGEN, If Grenades are full but HP is low, start regen
                elif self.player.grenades >= self.player.max_grenades and self.player.hp < 100:
                    self.player.regen_end_time = now + 2000 
                
                #Always refill grenades
                self.player.grenades = self.player.max_grenades
                
                #Effects
                self.create_explosion(px, py, BLUE)
                self.screen_shake(6)
                if pu in self.pickups: 
                    self.pickups.remove(pu)

        for particle in self.particles[:]:
            particle.update()
            if particle.is_dead():
                self.particles.remove(particle)

        if self.screen_shake_intensity > 0:
            self.screen_shake_intensity -= 1

        # VICTORY SEQUENCE LOGIC
        if self.boss_defeated:
            if pygame.time.get_ticks() - self.victory_timer > 2000:
                #Fade In
                self.fade_alpha += 1
                if self.fade_alpha >= 255:
                    self.state = GameState.GAME_OVER

    def draw_menu(self):
        if getattr(self, 'menu_bg', None):
            self.screen.blit(self.menu_bg, (0, 0))
        else:
            self.screen.fill(BLACK)

        title = self.font_large.render("FIGHTER JET DOGFIGHT", True, WHITE)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 80))
        self.screen.blit(title, title_rect)

      


        play_btn = pygame.Rect(SCREEN_WIDTH//2 - 120, 350, 240, 60)
        quit_btn = pygame.Rect(SCREEN_WIDTH//2 - 120, 430, 240, 60)

        pygame.draw.rect(self.screen, (60, 180, 255), self.play_btn, border_radius=30)
        pygame.draw.rect(self.screen, (220, 60, 60), self.quit_btn, border_radius=30)

        self.screen.blit(
            self.font_medium.render("PLAY", True, (255, 255, 255)),
            play_btn.move(80, 15)
        )
        self.screen.blit(
            self.font_medium.render("QUIT", True, (255, 255, 255)),
            quit_btn.move(80, 15)
        )

        controls1 = self.font_small.render("WASD/Arrows = Move", True, LIGHT_GRAY)
        controls1_rect = controls1.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120))
        self.screen.blit(controls1, controls1_rect)

        controls2 = self.font_small.render("SPACE = Shoot | F = Grenade | L-SHIFT = Dash", True, LIGHT_GRAY)
        controls2_rect = controls2.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80))
        self.screen.blit(controls2, controls2_rect)

        reload_tip = self.font_small.render("100 Bullets per clip - Auto-Reloads when empty", True, ORANGE)
        reload_tip_rect = reload_tip.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40))
        self.screen.blit(reload_tip, reload_tip_rect)

    def draw_game_over(self):
        self.screen.fill(BLACK)

        title = self.font_large.render("GAME OVER", True, RED)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 100))
        self.screen.blit(title, title_rect)

        kills_text = self.font_medium.render(f"Final Kills: {self.kills}", True, WHITE)
        kills_rect = kills_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(kills_text, kills_rect)

        wave_text = self.font_small.render(f"Wave Reached: {self.wave}", True, WHITE)
        wave_rect = wave_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
        self.screen.blit(wave_text, wave_rect)

        restart = self.font_small.render("Press R to Restart", True, GREEN)
        restart_rect = restart.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120))
        self.screen.blit(restart, restart_rect)

        quit_text = self.font_small.render("Press ESC to Quit", True, LIGHT_GRAY)
        quit_rect = quit_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80))
        self.screen.blit(quit_text, quit_rect)

    def draw_playing(self):
        current_time = pygame.time.get_ticks()
        shake_x, shake_y = 0, 0
        if self.screen_shake_intensity > 0:
            shake_x = random.randint(-self.screen_shake_intensity, self.screen_shake_intensity)
            shake_y = random.randint(-self.screen_shake_intensity, self.screen_shake_intensity)

        offset_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        if getattr(self, 'game_bg', None):
            offset_surf.blit(self.game_bg, (0, 0))
        else:
            offset_surf.fill((10, 10, 30))

        #DRAW OFFICERS
        for off in self.officers: 
            off.draw(offset_surf)

        #DRAW BOSS
        if self.boss:
            if getattr(self, 'boss_image', None) and getattr(self.boss, 'image', None) is None:
                self.boss.image = self.boss_image
            self.boss.draw(offset_surf, self.font_medium)

        #Pickups
        for pu in self.pickups:
            pu.draw(offset_surf)

        #Player
        self.player.draw(offset_surf, current_time)

        #Enemies (Minions)
        for enemy in self.enemies:
            enemy.draw(offset_surf)

        #Projectiles & Effects
        for bullet in self.bullets:
            bullet.draw(offset_surf)

        for particle in self.particles:
            particle.draw(offset_surf)

        #HUD & UI
        hp_bar_width = 300
        hp_bar_height = 25
        hp_x, hp_y = 20, 20
        pygame.draw.rect(offset_surf, DARK_GRAY, (hp_x, hp_y, hp_bar_width, hp_bar_height))
        hp_ratio = self.player.hp / self.player.max_hp
        hp_color = GREEN if hp_ratio > 0.5 else ORANGE if hp_ratio > 0.25 else RED
        pygame.draw.rect(offset_surf, hp_color, (hp_x, hp_y, int(hp_bar_width * hp_ratio), hp_bar_height))
        pygame.draw.rect(offset_surf, WHITE, (hp_x, hp_y, hp_bar_width, hp_bar_height), 2)

        #Ammo /Reload /Grenades
        ammo_y = hp_y + hp_bar_height + 10
        if self.player.is_reloading:
            reload_progress = min(1.0, (current_time - self.player.reload_start_time) / PLAYER_RELOAD_TIME)
            pygame.draw.rect(offset_surf, DARK_GRAY, (hp_x, ammo_y + 25, hp_bar_width, 10))
            pygame.draw.rect(offset_surf, YELLOW, (hp_x, ammo_y + 25, int(hp_bar_width * reload_progress), 10))
            ammo_text = self.font_small.render("RELOADING CLIP...", True, ORANGE)
            offset_surf.blit(ammo_text, (hp_x, ammo_y))
            grenade_y_pos = ammo_y + 45
        else:
            ammo_text = self.font_small.render(f"Ammo: {self.player.ammo}/{self.player.max_ammo}", True, WHITE)
            offset_surf.blit(ammo_text, (hp_x, ammo_y))
            grenade_y_pos = ammo_y + 30

        if self.player.grenades > 0:
            grenade_text = self.font_small.render(f"Grenades: {self.player.grenades}/{self.player.max_grenades}", True, ORANGE)
            offset_surf.blit(grenade_text, (hp_x, grenade_y_pos))

        #Stat HUD
        score_text = self.font_small.render(f"SCORE: {self.kills}", True, WHITE)
        offset_surf.blit(score_text, (SCREEN_WIDTH - 220, 20))
        kills_stat = self.font_small.render(f"KILLS: {self.total_kills}", True, GREEN)
        offset_surf.blit(kills_stat, (SCREEN_WIDTH - 220, 50))
        time_text = self.font_small.render(f"TIME: {self.elapsed_time}s", True, YELLOW)
        offset_surf.blit(time_text, (SCREEN_WIDTH - 220, 80))
        lives_text = self.font_small.render(f"LIVES: {self.player.lives + 1}", True, RED)
        offset_surf.blit(lives_text, (SCREEN_WIDTH - 220, 110))

        #Progress / Boss Logic
        if not self.boss:
            target = WAVE_1_TARGET if self.wave == 1 else WAVE_2_TARGET if self.wave == 2 else WAVE_3_TARGET
            prog_text = self.font_small.render(f"WAVE {self.wave} - Progress: {self.wave_progress}/{target}", True, LIGHT_GRAY)
            offset_surf.blit(prog_text, (SCREEN_WIDTH // 2 - 120, 15))

        #box Slot HUD
        now = pygame.time.get_ticks()
        is_cooldown = now < self.box_cooldown_timer
        for i in range(3):
            box_color = (50, 50, 50) if is_cooldown else (0, 200, 255) if i < self.box_slots else (20, 20, 20)
            pygame.draw.rect(offset_surf, box_color, (SCREEN_WIDTH//2 - 45 + (i*35), 45, 25, 25), 0 if i < self.box_slots else 2)

        if self.player.invincible_cheat:
            ch_text = self.font_small.render("GOD MODE", True, YELLOW)
            offset_surf.blit(ch_text, (20, SCREEN_HEIGHT - 40))

        #Draw Shockwave
        if self.shockwave_radius > 0 and self.shockwave_radius < SCREEN_WIDTH:
            self.shockwave_radius += 15
            pygame.draw.circle(offset_surf, WHITE, (int(self.player.x), int(self.player.y)), self.shockwave_radius, 3)

        self.screen.blit(offset_surf, (shake_x, shake_y))

        #DRAW FADE OVERLAY
        if self.boss_defeated and self.victory_timer > 0:
             if pygame.time.get_ticks() - self.victory_timer > 2000:
                fade_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                fade_surf.fill(BLACK)
                fade_surf.set_alpha(self.fade_alpha)
                self.screen.blit(fade_surf, (0, 0))
                
                if self.fade_alpha > 50:
                    txt = self.font_large.render("MISSION ACCOMPLISHED", True, GREEN)
                    txt.set_alpha(self.fade_alpha)
                    rect = txt.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
                    self.screen.blit(txt, rect)

        self.joystick.draw(self.screen)
        self.btn_shoot.draw(self.screen, self.font_small)
        self.btn_dash.draw(self.screen, self.font_small)
        self.btn_grenade.draw(self.screen, self.font_small)


    async def run(self):
        while self.running:
            self.handle_events()

            if self.state == GameState.PLAYING:
                self.update_playing()
                self.draw_playing()
            elif self.state == GameState.MENU:
                self.draw_menu()
            elif self.state == GameState.GAME_OVER:
                self.draw_game_over()

            pygame.display.flip()
            self.clock.tick(FPS)

            await asyncio.sleep(0)

        pygame.quit()


async def main():
    game = Game()
    await game.run()

if __name__ == "__main__":
    asyncio.run(main())

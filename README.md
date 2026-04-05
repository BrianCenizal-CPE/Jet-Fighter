# Project Goliath: Fighter Jet Boss-Rush

A robust, 2D combat prototype built with Python and Pygame. 

## Technical Highlights
- A 5-phase boss system ("Goliath Motherboard") with dynamic transitions, enrage timers, and different attack patterns.
- Implemented i-frames (invincibility frames), directional dashing, and a "stagger" vulnerability window for strategic gameplay.
- Utilized trigonometric functions (`sin`, `cos`, `atan2`) for homing projectiles and smooth entity tracking.
- Unified input handling supporting both Desktop (Keyboard) and Mobile (Touch/Virtual Joystick).
- Custom particle system and entity management to ensure stable FPS.

## Boss Mechanics (Goliath Motherboard)
1. **Phase 1 (Normal):** Basic cycle of linear and homing attacks.
2. **Phase 2 (Stagger):** Boss gains new attacks and visual telegraphing.
3. **Phase 3 (Officer Support):** Spawns defensive mini-bosses to create a bullet-hell-like environment.
4. **Phase 4 (Forcefield):** Shield-core logic requiring environmental interaction to damage.
5. **Phase 5 (Berserk):** High-speed, high-damage final stand with 0% stagger rate.

## Controls
- **Desktop:** `WASD` to move, `SPACE` to shoot, `F` for Grenades, `L-SHIFT` to Dash.
- **Mobile:** Virtual Joystick and dedicated touch buttons.
- **Debug (For PC only):** `P + 0` for Invincibility; `P + [1-6]` to skip waves.

## Project Structure
- `main.py`: Monolithic game engine and state management.
- `asset/`: Optimized sprite and background assets.
- `build/`: Mobile deployment artifacts (Android APK).

## Installation & Setup

To run this game locally on your machine, follow these steps:

### Prerequisites
- **Python 3.10 or higher**
- **Pygame-ce (or Pygame)**

### Setup Instructions
1. **Clone the Repository:**
   ```bash
   git clone https://github.com/BrianCenizal-CPE/Jet-Fighter.git
   cd Jet-Fighter

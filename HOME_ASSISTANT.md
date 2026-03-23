# Home Assistant Integration

Delulu Her can now control your smart home devices through Home Assistant!

## Setup Instructions

1. **Enable Home Assistant in `.env`**
   Open your `.env` file and set `HA_ENABLED=true`.

2. **Configure Connection Properties**
   - Set `HA_URL` to your Home Assistant URL (e.g., `http://homeassistant.local:8123` or your public Nabu Casa URL).
   - Generate a **Long-Lived Access Token** in your Home Assistant user profile (click your username at the bottom left, scroll down to "Long-Lived Access Tokens" and click "Create Token").
   - Set `HA_TOKEN=your_token_here` in your `.env` file.

3. **Device Auto-Discovery & Mapping**
   When the server starts, Delulu Her will connect to your Home Assistant instance and automatically discover your `switch`, `light`, and `fan` entities! 
   
   These devices and their friendly names will be saved to:
   `services/ha_config/device_map.json`
   
   If Delulu doesn't recognize a specific device, you can edit this mapping file manually. For example:
   ```json
   {
       "living room light": "light.living_room_lamp",
       "the fan": "fan.bedroom_fan",
       "desk lamp": "switch.sonoff_basic_1"
   }
   ```
   *Note: Only lowercase names are keys in the `device_map.json` file!*

## How to use

You can control devices via voice commands to Delulu. Make sure to use the configured device friendly-names!

- **To turn ON:**
  "Delulu, turn on the living room light."
  "Delulu, switch on the fan."

- **To turn OFF:**
  "Delulu, turn off the bedroom lamp."
  "Delulu, switch off the desk lights."

- **To toggle state:**
  "Delulu, toggle the bathroom lights."

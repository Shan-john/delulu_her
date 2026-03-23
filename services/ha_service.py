import json
import os
import requests
from typing import Dict, List, Optional
import config
from utils.logger import get_logger

log = get_logger("ha_service")

# Map of friendly names to actual Home Assistant entity IDs
DEVICE_MAP_FILE = config.BASE_DIR / "services" / "ha_config" / "device_map.json"
_device_map: Dict[str, str] = {}
_ha_headers: Optional[Dict[str, str]] = None

def fetch_devices_and_update_map():
    """Automatically fetch switches and lights from HA and update the JSON map."""
    if not config.HA_ENABLED or not _ha_headers:
        return
        
    try:
        entities = fetch_all_entities()
        updated = False
        for entity in entities:
            e_id = entity.get("entity_id", "")
            domain = e_id.split(".")[0]
            if domain in ["switch", "light", "fan", "group"]:
                # Try to get a friendly name from attributes
                attrs = entity.get("attributes", {})
                friendly = attrs.get("friendly_name", e_id.split(".")[1]).lower()
                
                # Default map name if not exists
                if friendly not in _device_map:
                    _device_map[friendly] = e_id
                    updated = True
                    log.info("Auto-discovered Home Assistant device: '%s' -> %s", friendly, e_id)
        
        if updated:
            with open(DEVICE_MAP_FILE, "w") as f:
                json.dump(_device_map, f, indent=4)
            log.info("Saved updated device map to %s.", DEVICE_MAP_FILE)
    except Exception as e:
        log.error("Error auto-discovering HA devices: %s", e)


def load_device_map():
    global _device_map
    if os.path.exists(DEVICE_MAP_FILE):
        try:
            with open(DEVICE_MAP_FILE, "r") as f:
                _device_map = json.load(f)
            log.info("Loaded %d devices from Home Assistant device map.", len(_device_map))
        except Exception as e:
            log.error("Failed to load Home Assistant device map (%s): %s", DEVICE_MAP_FILE, e)
    else:
        log.warning("Home Assistant device map not found: %s", DEVICE_MAP_FILE)


def init():
    global _ha_headers
    if not config.HA_ENABLED:
        log.info("Home Assistant integration is disabled.")
        return

    if not config.HA_TOKEN or not config.HA_URL:
        log.warning("Home Assistant is enabled, but HA_URL or HA_TOKEN is missing.")
        return

    _ha_headers = {
        "Authorization": f"Bearer {config.HA_TOKEN}",
        "Content-Type": "application/json"
    }

    load_device_map()
    fetch_devices_and_update_map()
    log.info("Home Assistant integration initialized.")


def fetch_all_entities() -> List[Dict]:
    """Fetch all available devices from Home Assistant."""
    if not _ha_headers:
        return []

    url = f"{config.HA_URL.rstrip('/')}/api/states"
    try:
        response = requests.get(url, headers=_ha_headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log.error("Failed to fetch devices from Home Assistant: %s", e)
        return []


def describe_available_devices() -> str:
    """Return a descriptive string of devices for the AI."""
    load_device_map()
    if not _device_map:
        return "No friendly device map is configured."
    res = []
    for friendly, entity in _device_map.items():
        res.append(f"'{friendly}' mapped to {entity}")
    return "\n".join(res)


def get_entity_state(entity_id: str) -> Optional[str]:
    """Get the current state (e.g. 'on' or 'off') of an entity."""
    if not _ha_headers:
        return None

    url = f"{config.HA_URL.rstrip('/')}/api/states/{entity_id}"
    try:
        response = requests.get(url, headers=_ha_headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("state")
    except Exception as e:
        log.error("Failed to fetch state for %s: %s", entity_id, e)
        return None


def call_service(domain: str, service: str, entity_id: str) -> bool:
    """Call a Home Assistant service for an entity."""
    if not _ha_headers:
        return False

    url = f"{config.HA_URL.rstrip('/')}/api/services/{domain}/{service}"
    payload = {"entity_id": entity_id}

    try:
        response = requests.post(url, headers=_ha_headers, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        log.error("Home Assistant failed to call %s.%s on %s: %s", domain, service, entity_id, e)
        return False


def _resolve_entity(friendly_name: str) -> Optional[str]:
    """Resolve a friendly name to an entity_id."""
    # Strict matching
    if friendly_name in _device_map:
        return _device_map[friendly_name]

    # Substring matching to allow 'the lights' to match 'lights'
    for key, entity in _device_map.items():
        if key in friendly_name.lower():
            return entity
            
    return None


def control_device(friendly_name: str, action: str) -> str:
    """
    Control a Home assistant device.
    `friendly_name` is from the device map.
    `action` should be 'on', 'off', or 'toggle'.
    Returns a TTS string describing the result.
    """
    if not config.HA_ENABLED:
        return "Sorry bestie, Home Assistant integration is not enabled!"

    entity_id = _resolve_entity(friendly_name)
    if not entity_id:
        # Give fallback string
        return f"Hmm, I don't know any device named '{friendly_name}', bestie. Make sure it's in the device map."

    domain = entity_id.split('.')[0]
    # some devices might be light. or switch. or group.
    # Supported services are typically turn_on, turn_off, toggle
    if action == 'on':
        service = "turn_on"
    elif action == 'off':
        service = "turn_off"
    else:
        service = "toggle"

    success = call_service(domain, service, entity_id)
    if success:
        return f"Okay bestie, I've turned {action} the {friendly_name}!"
    else:
        return f"Uh oh! I couldn't reach Home Assistant to turn {action} the {friendly_name}."

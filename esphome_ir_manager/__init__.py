import json
import os
import logging
import voluptuous as vol
import re
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.components.recorder import history
import homeassistant.util.dt as dt_util

from .const import DOMAIN, STORAGE_PATH

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["select"]

async def async_setup_entry(hass: HomeAssistant, entry):
    """Setup integration with localization and robust logic."""
    
    configured_listeners = entry.options.get("listeners", entry.data.get("listeners", []))
    hass.data.setdefault(DOMAIN, {"listeners": configured_listeners, "select_entity": None})

    def load_codes_sync():
        if not os.path.exists(STORAGE_PATH): return {}
        try:
            with open(STORAGE_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception: return {}

    def save_codes_sync(db):
        with open(STORAGE_PATH, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4)

    async def async_update_library_manager():
        """Update library entity for UI selectors."""
        db = await hass.async_add_executor_job(load_codes_sync)
        attr = {}
        for name, data in db.items():
            if isinstance(data, dict):
                r = data.get("repeat", 1)
                d = data.get("data", {})
                attr[name] = f"ADDR:{d.get('address')}|CMD:{d.get('command')} (Rep:{r})"
        hass.states.async_set(f"{DOMAIN}.library_manager", str(len(db)), attr)

    async def async_import_historic_data():
        """Import historical signals from recorder on startup."""
        history_entity = f"{DOMAIN}.history_manager"
        attr = {}
        if "recorder" in hass.config.components:
            for entity_id in configured_listeners:
                end_time = dt_util.now()
                start_time = end_time - timedelta(days=3)
                states = await hass.async_add_executor_job(
                    history.get_significant_states, hass, start_time, end_time, [entity_id]
                )
                if states and entity_id in states:
                    for state in reversed(states[entity_id]):
                        if state.state and state.state.startswith("ADDR:"):
                            if state.state not in attr:
                                attr[state.state] = state.last_changed.strftime("%H:%M:%S")
                        if len(attr) >= 10: break
        hass.states.async_set(history_entity, "Ready", attr)

    @callback
    def async_handle_sensor_update(event):
        """Live update history on new reception."""
        entity_id = event.data.get("entity_id")
        if entity_id in hass.data[DOMAIN]["listeners"]:
            new_state = event.data.get("new_state")
            if not new_state or not new_state.state or not new_state.state.startswith("ADDR:"):
                return
            history_entity = f"{DOMAIN}.history_manager"
            current = hass.states.get(history_entity)
            attr = {k: v for k, v in current.attributes.items() if k.startswith("ADDR:")} if current else {}
            attr[new_state.state] = dt_util.now().strftime("%H:%M:%S")
            if len(attr) > 10:
                oldest = sorted(attr.items(), key=lambda x: x[1])[0][0]
                attr.pop(oldest)
            hass.states.async_set(history_entity, "Receiving", attr)

    await async_import_historic_data()
    await async_update_library_manager()

    entry.async_on_unload(hass.bus.async_listen("state_changed", async_handle_sensor_update))

    # --- SERVICES ---

    async def async_save_code(call: ServiceCall):
        """Save code and clean '0x' prefix."""
        name = call.data.get("name")
        selected_code = call.data.get("selected_code")
        repeat = call.data.get("repeat", 1)
        if not selected_code or "|" not in selected_code: return
        
        try:
            parts = selected_code.split("|")
            addr_val = parts[0].split(":")[1].replace("0x", "")
            cmd_val = parts[1].split(":")[1].replace("0x", "")
            
            db = await hass.async_add_executor_job(load_codes_sync)
            db[name] = {
                "type": "NEC",
                "repeat": int(repeat),
                "data": {"address": addr_val, "command": cmd_val}
            }
            await hass.async_add_executor_job(save_codes_sync, db)
            await async_update_library_manager()
            if hass.data[DOMAIN]["select_entity"]:
                await hass.data[DOMAIN]["select_entity"].async_update_from_file()
        except Exception as e:
            _LOGGER.error("Error saving code: %s", e)

    async def async_send_code(call: ServiceCall):
        """Send code with robust hex conversion."""
        name = call.data.get("name")
        target_data = call.data.get("target_action")
        
        target_service = None
        if isinstance(target_data, list) and len(target_data) > 0:
            target_service = target_data[0].get("action") or target_data[0].get("service")
        elif isinstance(target_data, dict):
            target_service = target_data.get("action") or target_data.get("service")
        else:
            target_service = target_data

        if not target_service or "." not in str(target_service):
            _LOGGER.error("Invalid service: %s", target_data)
            return

        db = await hass.async_add_executor_job(load_codes_sync)
        if name in db:
            d = db[name]["data"]
            repeat = db[name].get("repeat", 1)
            
            def to_int(val):
                s = str(val).strip()
                if "0x" in s.lower() or any(c in s.upper() for c in "ABCDEF"):
                    return int(s, 16)
                return int(s)

            try:
                domain, svc = target_service.split(".")
                await hass.services.async_call(domain, svc, {
                    "address": to_int(d["address"]),
                    "command": to_int(d["command"]),
                    "repeats": int(repeat)
                })
                _LOGGER.info("IR code '%s' sent successfully", name)
            except Exception as e:
                _LOGGER.error("Send error for '%s': %s", name, e)

    async def async_manage_library(call: ServiceCall):
        """Manage library codes."""
        action, target_name, new_name = call.data.get("action"), call.data.get("target_name"), call.data.get("new_name")
        db = await hass.async_add_executor_job(load_codes_sync)
        if target_name in db:
            if action == "Delete": del db[target_name]
            elif action == "Rename" and new_name: db[new_name] = db.pop(target_name)
            await hass.async_add_executor_job(save_codes_sync, db)
            await async_update_library_manager()
            if hass.data[DOMAIN]["select_entity"]:
                await hass.data[DOMAIN]["select_entity"].async_update_from_file()

    hass.services.async_register(DOMAIN, "save_code", async_save_code)
    hass.services.async_register(DOMAIN, "send_code", async_send_code)
    hass.services.async_register(DOMAIN, "manage_library", async_manage_library)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
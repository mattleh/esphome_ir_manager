import json
import os
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, STORAGE_PATH

async def async_setup_entry(hass, entry, async_add_entities):
    entity = IRLibrarySelect(hass, entry)
    hass.data[DOMAIN]["select_entity"] = entity
    async_add_entities([entity])

class IRLibrarySelect(SelectEntity):
    """Select entity to choose an IR command from the library."""

    has_entity_name = True
    _attr_translation_key = "library_selector"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass, entry):
        self.hass = hass
        self._attr_unique_id = f"{entry.entry_id}_library_selector"
        self._attr_options = []
        self._attr_current_option = None

    async def async_added_to_hass(self):
        await self.async_update_from_file()

    async def async_update_from_file(self):
        def load():
            if not os.path.exists(STORAGE_PATH): return []
            try:
                with open(STORAGE_PATH, 'r') as f:
                    return sorted(list(json.load(f).keys()))
            except: return []

        options = await self.hass.async_add_executor_job(load)
        self._attr_options = options
        if options and (self._attr_current_option not in options):
            self._attr_current_option = options[0]
        self.async_write_ha_state()

    async def async_select_option(self, option: str):
        self._attr_current_option = option
        self.async_write_ha_state()
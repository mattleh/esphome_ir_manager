from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN

class ESPHomeIRManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESPHome IR Manager."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="IR Manager", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("listeners"): cv.entity_ids,
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ESPHomeIRManagerOptionsFlow(config_entry)

class ESPHomeIRManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow to update listeners."""
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    "listeners", 
                    default=self.config_entry.options.get(
                        "listeners", self.config_entry.data.get("listeners")
                    )
                ): cv.entity_ids,
            })
        )
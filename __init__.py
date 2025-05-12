"""Modbus Charger integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration (only called for YAML mode)."""
    # We handle everything via config entries
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a config entry (called by the UI)."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    _LOGGER.debug("Modbus Charger config entry set up: %s", entry.entry_id)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    try:
        # Use newer API to unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    except Exception as err:
        _LOGGER.error("Error unloading modbus_charger entry: %s", err)
        return False

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("Modbus Charger config entry unloaded: %s", entry.entry_id)

    return unload_ok
"""Modbus Charger integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_SLAVE_ID
from .read_device_info import identify_subdevices

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration (only called for YAML mode)."""
    # We handle everything via config entries
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a config entry (called by the UI)."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 502)
    slave = entry.data.get(CONF_SLAVE_ID, 82)

    # Quick connectivity check: try to identify subdevices once
    try:
        # Run in executor to avoid blocking
        chargers = await hass.async_add_executor_job(
            identify_subdevices,
            host,
            port,
            slave,
            3  # small timeout for quick check
        )
        if not chargers:
            _LOGGER.warning("No EMMA CHARGER sub-devices found at %s:%s", host, port)
    except Exception as e:
        _LOGGER.error("Failed to connect to EMMA Charger at %s:%s: %s", host, port, e)
        # Inform HA to retry later
        raise ConfigEntryNotReady from e

    # Store config & forward to sensor platform
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    _LOGGER.debug("Huawei Emma Charger config entry set up: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    except Exception as err:
        _LOGGER.error("Error unloading Huawei Emma Charger entry: %s", err)
        return False

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("Huawei Emma Charger config entry unloaded: %s", entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)

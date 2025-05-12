'''Config flow for Modbus Charger integration.'''
import voluptuous as vol
from pymodbus.client import ModbusTcpClient
import asyncio
from homeassistant import config_entries, exceptions

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
)

# Schema for user input in the config flow
DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
})

class ModbusChargerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    '''Handle a config flow for the Modbus Charger integration.'''

    VERSION = 1

    async def async_step_user(self, user_input=None):
        '''Handle the initial step where the user provides connection info.'''
        errors = {}
        if user_input is not None:
            try:
                # Test connectivity to the charger
                await self._test_connection(user_input)
            except CannotConnect:
                errors['base'] = 'cannot_connect'
            except Exception:
                errors['base'] = 'unknown'
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id='user',
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, data):
        '''Attempt to connect to the Modbus charger using pymodbus.'''
        host = data[CONF_HOST]
        port = data.get(CONF_PORT, DEFAULT_PORT)
        timeout = 3.0

        def try_connect():
            client = ModbusTcpClient(host, port=port, timeout=timeout)
            connected = client.connect()
            client.close()
            if not connected:
                raise CannotConnect
            return True

        # Run blocking IO in executor
        return await self.hass.async_add_executor_job(try_connect)

class CannotConnect(exceptions.HomeAssistantError):
    '''Error to indicate we cannot connect to the charger.'''
    pass
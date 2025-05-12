import logging
from datetime import timedelta
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SLAVE, CONF_SCAN_INTERVAL

from .const import DOMAIN, SENSOR_TYPES
from .read_device_info import identify_subdevices

_LOGGER = logging.getLogger(__name__)


class HuaweiEmmaChargerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str, port: int, slave: int, scan_interval: timedelta):
        super().__init__(
            hass,
            _LOGGER,
            name="Huawei EMMA Charger",
            update_interval=scan_interval,
        )
        self.host = host
        self.port = port
        self.slave = slave

    def _read_registers(self, slave_id: int, address: int, count: int):
        client = ModbusTcpClient(self.host, port=self.port)
        try:
            if not client.connect():
                raise ConnectionError(f"Modbus connect failed to {self.host}:{self.port}")
            response = client.read_holding_registers(address, count, unit=slave_id)
            if isinstance(response, ExceptionResponse) or response.isError():
                raise ModbusException(f"Error reading registers: {response}")
            return response.registers
        finally:
            client.close()

    async def _async_update_data(self):
        data = {}
        # Discover charger sub-devices dynamically
        chargers = await self.hass.async_add_executor_job(
            identify_subdevices,
            self.host,
            self.port,
            self.slave,
            self.update_interval.total_seconds(),
        )
        for charger in chargers:
            sid = charger["slave_id"]
            for sensor_key, name, unit, reg_type, address, count in SENSOR_TYPES:
                try:
                    regs = await self.hass.async_add_executor_job(
                        self._read_registers, sid, address, count
                    )
                    value = _convert(regs, reg_type)
                    data_key = f"{sensor_key}_{sid}"
                    data[data_key] = {
                        "name": f"{name} (Slave {sid})",
                        "value": value,
                        "unit": unit,
                        "slave_id": sid,
                    }
                except Exception as err:
                    _LOGGER.error("Error reading sensor %s for slave %s: %s", sensor_key, sid, err)
        return data


def _convert(registers: list[int], reg_type: str):
    if reg_type == "u16":
        return registers[0]
    if reg_type == "s16":
        v = registers[0]
        return v if v < 0x8000 else v - 0x10000
    if reg_type == "u32":
        return (registers[0] << 16) + registers[1]
    if reg_type == "float":
        import struct

        b = struct.pack('>HH', registers[0], registers[1])
        return struct.unpack('>f', b)[0]
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 502)
    slave = entry.data.get(CONF_SLAVE, 1)
    interval_seconds = entry.data.get(CONF_SCAN_INTERVAL, 30)
    scan_interval = timedelta(seconds=interval_seconds)

    coordinator = HuaweiEmmaChargerCoordinator(hass, host, port, slave, scan_interval)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("First refresh failed: %s", err)
        raise

    entities = []
    for data_key in coordinator.data:
        entities.append(HuaweiEmmaChargerSensor(coordinator, data_key))

    async_add_entities(entities)


class HuaweiEmmaChargerSensor(CoordinatorEntity):
    def __init__(self, coordinator: HuaweiEmmaChargerCoordinator, data_key: str):
        super().__init__(coordinator)
        self.data_key = data_key
        sensor_info = coordinator.data[data_key]
        self._name = sensor_info["name"]
        self._unit = sensor_info["unit"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self):
        return self.coordinator.data.get(self.data_key, {}).get("value")

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.data_key}"

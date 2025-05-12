import logging
from datetime import timedelta
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    SENSOR_TYPES,
)
from .read_device_info import identify_subdevices

_LOGGER = logging.getLogger(__name__)


class HuaweiEmmaChargerCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: timedelta,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Huawei EMMA Charger",
            update_interval=scan_interval,
        )
        self.host = host
        self.port = port
        self.slave_id = slave_id

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
            self.slave_id,
            int(self.update_interval.total_seconds()),
        )
        for charger in chargers:
            sid = charger["slave_id"]
            for sensor_key, name, address, quantity, reg_type, gain, unit in SENSOR_TYPES:
                try:
                    regs = await self.hass.async_add_executor_job(
                        self._read_registers, sid, address, quantity
                    )
                    value = _convert(regs, reg_type, gain)
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


def _convert(registers: list[int], reg_type: str, gain: int):
    """Convert register values based on type and gain."""
    if reg_type == "STR":
        # Concatenate registers into bytes and decode ascii
        raw_bytes = b"".join(reg.to_bytes(2, "big") for reg in registers)
        return raw_bytes.decode("ascii", errors="ignore").rstrip("\x00")
    if reg_type == "U32":
        raw = (registers[0] << 16) + registers[1]
        return raw / gain
    if reg_type == "I32":
        import struct

        b = struct.pack(">HH", registers[0], registers[1])
        raw = struct.unpack(">i", b)[0]
        return raw / gain
    _LOGGER.warning("Unknown register type %s", reg_type)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    slave_id = entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
    interval_seconds = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(seconds=interval_seconds)

    coordinator = HuaweiEmmaChargerCoordinator(hass, host, port, slave_id, scan_interval)
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

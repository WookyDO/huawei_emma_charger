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
    """Coordinator to fetch Modbus data and compute instantaneous power."""

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
        self._last_energy: dict[int, float] = {}

    def _read_registers(self, slave: int, address: int, count: int) -> list[int]:
        client = ModbusTcpClient(self.host, port=self.port)
        try:
            if not client.connect():
                raise ConnectionError(f"Modbus connect failed to {self.host}:{self.port}")
            response = client.read_holding_registers(address=address, count=count, slave=slave)
            if isinstance(response, ExceptionResponse) or response.isError():
                raise ModbusException(f"Error reading registers: {response}")
            return response.registers
        finally:
            client.close()

    async def _async_update_data(self) -> dict[str, dict]:
        data: dict[str, dict] = {}
        # Discover subdevices
        chargers = await self.hass.async_add_executor_job(
            identify_subdevices,
            self.host,
            self.port,
            self.slave_id,
            int(self.update_interval.total_seconds()),
        )
        for charger in chargers:
            sid = charger["slave_id"]
            # read sensors
            for key, name, addr, qty, rtype, gain, unit in SENSOR_TYPES:
                try:
                    regs = await self.hass.async_add_executor_job(
                        self._read_registers, sid, addr, qty
                    )
                    value = _convert(regs, rtype, gain)
                    data_key = f"{key}_{sid}"
                    data[data_key] = {"name": f"{name} (Slave {sid})", "value": value, "unit": unit}
                except Exception as e:
                    _LOGGER.error("Error reading %s from slave %s: %s", key, sid, e)
            # compute instantaneous power if total_energy present
            tot_key = f"total_energy_{sid}"
            inst_key = f"instant_power_{sid}"
            if tot_key in data:
                curr = data[tot_key]["value"]
                prev = self._last_energy.get(sid)
                if prev is None:
                    # first cycle
                    power = 0.0
                else:
                    delta = curr - prev  # kWh delta
                    secs = self.update_interval.total_seconds()
                    power = (delta * 3600.0) / secs
                data[inst_key] = {"name": f"Instantaneous Power (Slave {sid})", "value": round(power, 3), "unit": "kW"}
                self._last_energy[sid] = curr
        return data


def _convert(regs: list[int], rtype: str, gain: int):
    if rtype == "STR":
        raw = b"".join(r.to_bytes(2, "big") for r in regs)
        return raw.decode("ascii", errors="ignore").rstrip("\x00")
    if rtype == "U32":
        val = (regs[0] << 16) | regs[1]
        return val / gain
    if rtype == "I32":
        import struct
        b = struct.pack(">HH", regs[0], regs[1])
        val = struct.unpack(">i", b)[0]
        return val / gain
    _LOGGER.warning("Unknown type %s", rtype)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    slave = entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
    interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coord = HuaweiEmmaChargerCoordinator(hass, host, port, slave, timedelta(seconds=interval))
    await coord.async_config_entry_first_refresh()
    ents = [HuaweiEmmaChargerSensor(coord, key) for key in coord.data]
    async_add_entities(ents)


class HuaweiEmmaChargerSensor(CoordinatorEntity):
    def __init__(self, coordinator: HuaweiEmmaChargerCoordinator, data_key: str):
        super().__init__(coordinator)
        info = coordinator.data[data_key]
        self._key = data_key
        self._name = info["name"]
        self._unit = info.get("unit")

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self):
        return self.coordinator.data[self._key]["value"]

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._key}"

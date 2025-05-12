import logging
from datetime import datetime, timedelta
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo

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

# Home Assistant state class constants (avoid import issues)
STATE_CLASS_MEASUREMENT = "measurement"
STATE_CLASS_TOTAL_INCREASING = "total_increasing"

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
        self._last_time: dict[int, datetime] = {}
        self._last_power: dict[int, float] = {}

    def _read_registers(self, slave: int, address: int, count: int) -> list[int]:
        """Read holding registers from the device."""
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
        """Fetch data and compute instantaneous power for each charger."""
        data: dict[str, dict] = {}
        chargers = await self.hass.async_add_executor_job(
            identify_subdevices,
            self.host,
            self.port,
            self.slave_id,
            int(self.update_interval.total_seconds()),
        )

        for charger in chargers:
            sid = charger["slave_id"]
            # Read all defined sensors
            for key, name, address, quantity, rtype, gain, unit in SENSOR_TYPES:
                data_key = f"{key}_{sid}"
                try:
                    regs = await self.hass.async_add_executor_job(
                        self._read_registers, sid, address, quantity
                    )
                    value = _convert(regs, rtype, gain)
                    data[data_key] = {"name": name, "value": value, "unit": unit, "rtype": rtype, "slave_id": sid}
                except Exception as err:
                    _LOGGER.error("Error reading %s from slave %s: %s", key, sid, err)

            # Compute instantaneous power
            tot_key = f"total_energy_{sid}"
            inst_key = f"instant_power_{sid}"
            if tot_key in data:
                curr = data[tot_key]["value"]
                now = datetime.utcnow()
                prev = self._last_energy.get(sid)
                last_power = self._last_power.get(sid, 0.0)

                # calculate elapsed seconds since last reading
                prev_time = self._last_time.get(sid)
                if prev_time:
                    secs = (now - prev_time).total_seconds()
                else:
                    secs = self.update_interval.total_seconds()

                # energy delta (kWh), clamp negative
                if prev is None:
                    delta = 0.0
                else:
                    delta = curr - prev
                    if delta < 0:
                        _LOGGER.debug(
                            "Energy counter rollover or reset for slave %s: curr=%s prev=%s",
                            sid, curr, prev
                        )
                        delta = 0.0

                # compute elapsed hours
                elapsed_h = secs / 3600.0 if secs > 0 else 0

                # compute or reuse last non-zero power
                power = (delta / elapsed_h) if delta > 0 and elapsed_h > 0 else last_power
                _LOGGER.debug(
                    "Energy counter calculated for slave %s after %s secs: curr=%s prev=%s power=%s",
                    sid, secs, curr, prev, power
                )

                data[inst_key] = {
                    "name": "Instantaneous Power",
                    "value": round(power, 3),
                    "unit": "kW",
                    "rtype": "U32",
                    "slave_id": sid,
                }

                # store for next cycle
                self._last_energy[sid] = curr
                self._last_time[sid] = now
                if power > 0:
                    self._last_power[sid] = power

        return data


def _convert(regs: list[int], rtype: str, gain: int):
    """Convert raw register values based on type and gain."""
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
    """Set up the sensors from the config entry."""
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    slave = entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
    interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = HuaweiEmmaChargerCoordinator(
        hass, host, port, slave, timedelta(seconds=interval)
    )
    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = []
    for key, info in coordinator.data.items():
        rtype = info.get("rtype")
        unit = info.get("unit")
        slave_id = info.get("slave_id")
        # Determine device_class & state_class
        device_class = None
        state_class = None
        if rtype != "STR":
            if unit == "kWh":
                device_class = SensorDeviceClass.ENERGY
                state_class = STATE_CLASS_TOTAL_INCREASING
            elif unit == "kW":
                device_class = SensorDeviceClass.POWER
                state_class = STATE_CLASS_MEASUREMENT
            elif unit == "V":
                device_class = SensorDeviceClass.VOLTAGE
                state_class = STATE_CLASS_MEASUREMENT
            elif unit == "°C":
                device_class = SensorDeviceClass.TEMPERATURE
                state_class = STATE_CLASS_MEASUREMENT
        entity = HuaweiEmmaChargerSensor(
            coordinator,
            key,
            info.get("name"),
            rtype,
            unit,
            device_class,
            state_class,
            slave_id,
        )
        entities.append(entity)
    async_add_entities(entities)


class HuaweiEmmaChargerSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for Huawei EMMA Charger readings."""

    def __init__(
        self,
        coordinator: HuaweiEmmaChargerCoordinator,
        data_key: str,
        name: str,
        rtype: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        state_class: str | None,
        slave_id: int,
    ):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.host}_{slave_id}" )},
            name=f"Huawei Charger {slave_id}",
            manufacturer="Huawei",
            model="EMMA Charger",
        )
        self._attr_name = f"{name} (Slave {slave_id})"
        if rtype == 

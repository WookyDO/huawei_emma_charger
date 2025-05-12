"""Sensor platform for Modbus Charger."""
import logging
from datetime import timedelta

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    REGISTER_DEFS,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_SCAN_INTERVAL,
)

# Home Assistant state class constants (avoid import issues)
STATE_CLASS_MEASUREMENT = "measurement"
STATE_CLASS_TOTAL_INCREASING = "total_increasing"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up sensors from a config entry."""
    try:
        config = entry.data
        host = config[CONF_HOST]
        port = config.get(CONF_PORT, DEFAULT_PORT)
        slave = config.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
        interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        coordinator = ModbusChargerDataUpdateCoordinator(
            hass, host, port, slave, interval
        )
        await coordinator.async_refresh()
    except UpdateFailed as err:
        _LOGGER.error("Initial connection to charger failed: %s", err)
        raise ConfigEntryNotReady from err
    except Exception as err:
        _LOGGER.exception("Error setting up Modbus Charger sensors")
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entities = [
        ModbusChargerSensor(
            coordinator,
            key,
            name,
            rtype,
            unit,
        )
        for key, name, _, _, rtype, _, unit in REGISTER_DEFS
    ]
    # Add instantaneous power sensor
    entities.append(ModbusChargerPowerSensor(coordinator))
    async_add_entities(entities, update_before_add=True)


class ModbusChargerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Modbus data."""

    def __init__(self, hass, host, port, slave, interval):
        update_interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.host = host
        self.port = port
        self.slave = slave

    async def _async_update_data(self):
        """Fetch data from the charger."""
        try:
            return await self.hass.async_add_executor_job(self._read_all)
        except Exception as err:
            raise UpdateFailed(f"Error reading charger: {err}") from err

    def _read_all(self):
        client = ModbusTcpClient(self.host, port=self.port)
        if not client.connect():
            raise UpdateFailed(f"Cannot connect to {self.host}:{self.port}")

        data = {}
        try:
            for key, name, addr, qty, rtype, gain, unit in REGISTER_DEFS:
                _LOGGER.debug("Reading %s @ %s", name, addr)
                try:
                    rr = client.read_holding_registers(addr, count=qty, slave=self.slave)
                except ModbusIOException as ex:
                    _LOGGER.warning("No response for %s: %s", name, ex)
                    continue

                if rr.isError():
                    _LOGGER.warning("Modbus error for %s: %s", name, rr)
                    continue

                regs = rr.registers
                raw_bytes = b"".join(r.to_bytes(2, byteorder="big") for r in regs)

                if rtype == "STR":
                    text = raw_bytes.decode("ascii", errors="ignore").rstrip("\x00")
                    data[key] = (text, unit)
                else:
                    raw = (regs[0] << 16) | regs[1]
                    if rtype == "I32" and raw & 0x80000000:
                        raw -= 1 << 32
                    scaled = raw / gain
                    data[key] = (scaled, unit)
        finally:
            client.close()

        return data


class ModbusChargerSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single charger register as sensor using CoordinatorEntity."""

    def __init__(self, coordinator, key, name, rtype, unit):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Charger {name}"
        self._attr_unique_id = f"modbus_charger_{key}"
        self._rtype = rtype

        # Configure attributes differently for string vs numeric sensors
        if rtype == "STR":
            # String sensor: no unit or state/device class
            self._attr_native_unit_of_measurement = None
            self._attr_state_class = None
            self._attr_device_class = None
        else:
            # Numeric sensor: set unit and state/device class
            self._attr_native_unit_of_measurement = unit
            lower_unit = unit.lower()
            if lower_unit == "kwh":
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
            elif lower_unit == "kw":
                self._attr_device_class = SensorDeviceClass.POWER
                self._attr_state_class = STATE_CLASS_MEASUREMENT
            elif lower_unit == "v":
                self._attr_device_class = SensorDeviceClass.VOLTAGE
                self._attr_state_class = STATE_CLASS_MEASUREMENT
            elif lower_unit in ("°c", "c"):
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_state_class = STATE_CLASS_MEASUREMENT
            else:
                self._attr_state_class = STATE_CLASS_MEASUREMENT

        # Associate all sensors with a single charger device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.host}_{coordinator.slave}" )},
            name="Modbus Charger",
            manufacturer="Generic",
            model="Modbus Charger",
        )

    @property
    def available(self):
        """Return if the sensor data is available."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """Return the current sensor value."""
        entry = self.coordinator.data.get(self._key)
        if entry is None:
            return None
        raw, _unit = entry
        # Return raw string or numeric scaled value
        return raw


# Add instantaneous charging power sensor
from homeassistant.util.dt import utcnow

class ModbusChargerPowerSensor(CoordinatorEntity, SensorEntity):
    """Sensor to compute instantaneous charging power in kW."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Charger Instant Power"
        self._attr_unique_id = f"modbus_charger_instant_power_{coordinator.host}_{coordinator.slave}"
        self._attr_native_unit_of_measurement = "kW"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = STATE_CLASS_MEASUREMENT

        self._prev_energy = None
        self._prev_time = None

    @property
    def available(self):
        """Return if the sensor data is available."""
        # available when coordinator has success and energy data
        return self.coordinator.last_update_success and \
            self.coordinator.data.get("total_energy") is not None

    @property
    def native_value(self):
        """Compute and return instantaneous power based on total_energy changes."""
        entry = self.coordinator.data.get("total_energy")
        if entry is None:
            return None
        current_energy = entry[0]  # in kWh
        now = utcnow()

        if self._prev_energy is None or self._prev_time is None:
            # First reading, initialize
            self._prev_energy = current_energy
            self._prev_time = now
            return None

        # Calculate time delta in hours
        delta_hours = (now - self._prev_time).total_seconds() / 3600
        if delta_hours <= 0:
            return None

        # Calculate energy delta and power
        delta_energy = current_energy - self._prev_energy
        power = delta_energy / delta_hours

        # Update previous for next calculation
        self._prev_energy = current_energy
        self._prev_time = now

        return round(power, 2)
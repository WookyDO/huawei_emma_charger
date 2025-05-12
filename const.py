"""Constants for the Huawei Emma Charger integration."""

DOMAIN = "huawei_emma_charger"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 82
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Register definitions: (key, name, address, quantity, type, gain, unit)
SENSOR_TYPES = [
    ("offering_name",   "Offering name",   30000, 15, "STR",   1,   ""),
    ("esn",             "ESN",             30015, 16, "STR",   1,   ""),
    ("software_version","Software version",30031,16, "STR",   1,   ""),
    ("rated_power",     "Rated power",     30076, 2, "U32",  10,  "kW"),
    ("charger_model",   "Charger model",   30078, 14, "STR",   1,   ""),
    ("bluetooth_name",  "Bluetooth name",  30094, 16, "STR",   1,   ""),
    ("phase_a_voltage", "Phase A voltage", 30500, 2, "U32",  10,  "V"),
    ("phase_b_voltage", "Phase B voltage", 30502, 2, "U32",  10,  "V"),
    ("phase_c_voltage", "Phase C voltage", 30504, 2, "U32",  10,  "V"),
    ("total_energy",    "Total energy",    30506, 2, "U32",1000, "kWh"),
    ("charger_temp",    "Charger temp.",   30508, 2, "I32",  10,  "°C"),
]
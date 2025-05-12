# Huawei Emma Charger Integration for Home Assistant

Custom integration to read data for Huawei FusionCharge from Huawei EMMA sub_device over Modbus TCP using `pymodbus`, exposing registers as entities and computing instantaneous charging power.

---

## Features

* **Modbus polling** of charger registers (strings & numerics)
* **Instantaneous Power** sensor (`sensor.charger_instant_power`) calculating kW from energy deltas
* **Autodiscovery of EMMA sub-devices**  
  Automatically finds all attached “CHARGER” sub-devices and instantiates sensors for each slave ID.  

---

## Installation

### Install via HACS

1. In Home Assistant, go to **HACS → Integrations**.
2. Click the three dots (⋮) → **Custom repositories**.
3. Enter repository URL: `https://github.com/wookydo/huawei_emma_charger` and select **Integration**.
4. Click **Add**.
5. In HACS Integrations, search for **Huawei Emma Charger** and install.
6. Restart Home Assistant.

### Manual Install

1. Copy the folder `custom_components/huawei_emma_charger/` into your Home Assistant **config/** directory.
2. Ensure `pymodbus>=2.5.3` is available (add to `requirements.txt` if necessary).
3. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Huawei Emma Charger**.
3. Fill in:

   * **Host**: EMMA IP/hostname
   * **Port**: Modbus TCP port (default `502`)
   * **Slave ID**: EMMA Modbus address (default `0`)
   * **Scan Interval**: Polling interval in seconds (default `30`)
4. Finish to add your charger.

Sensors will be created automatically, including the instant power sensor.

---

## Entities

* `sensor.charger_offering_name` *(string)*
* `sensor.charger_esn` *(string)*
* `sensor.charger_software_version` *(string)*
* `sensor.charger_rated_power` *(numeric, kW)*
* `sensor.charger_charger_model` *(string)*
* `sensor.charger_bluetooth_name` *(string)*
* `sensor.charger_phase_a_voltage` *(numeric, V)*
* `sensor.charger_phase_b_voltage` *(numeric, V)*
* `sensor.charger_phase_c_voltage` *(numeric, V)*
* `sensor.charger_total_energy` *(numeric, kWh)*
* `sensor.charger_charger_temp` *(numeric, °C)*
* `sensor.charger_instant_power` *(numeric, kW)*

---

## Troubleshooting

* Verify charger accessibility on the Modbus TCP host/port.
* Check logs under `[custom_components.huawei_emma_charger.*]` for errors.
* If used alongside `huawei_solar`, run a **Modbus proxy** (e.g. `modbus-proxy`, `socat`) to multiplex connections.

---

## Development & Contributions

Report issues or contribute at the GitHub repo: [https://github.com/wookydo/huawei\_emma\_charger](https://github.com/wookydo/huawei_emma_charger)

---

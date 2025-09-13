This project is archived as same data now as part of huawei_solar integration (starting with 1.6beta) I will not continue here as all features are now part of one integration.


# Huawei Emma Charger Integration for Home Assistant

Custom integration to read data for Huawei FusionCharge from the EMMA sub-device over Modbus TCP using `pymodbus`, exposing registers as entities.

---

## 🔍 Features

* **Modbus polling** of charger registers (strings & numerics)
* **Autodiscovery of EMMA sub-devices**
  Automatically finds all attached “CHARGER” sub-devices and instantiates sensors for each slave ID.

---

## 🛠 Installation

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

## ⚙️ Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Huawei Emma Charger**.
3. Fill in:

   * **Host**: EMMA IP/hostname
   * **Port**: Modbus TCP port (default `502`)
   * **Slave ID**: EMMA Modbus address (default `0`)
   * **Scan Interval**: Polling interval in seconds (default `30`)
4. Finish to add your charger.

Devices and sensors will be created automatically:

1. **One Device per Charger** (e.g. “Huawei Charger 82”), with all slave’s sensors grouped under it.
2. **Sensors** for each register per slave.

---

## 📋 Entities

For each slave device you get:

| Sensor key                  | Type    | Unit | Description                  |
| --------------------------- | ------- | ---- | ---------------------------- |
| `offering_name_<slave>`     | string  | —    | Charger offering name        |
| `device_name_<slave>`       | string  | —    | Device name                  |
| `esn_<slave>`               | string  | —    | Charger ESN                  |
| `software_version_<slave>`  | string  | —    | Firmware version             |
| `rated_power_<slave>`       | numeric | kW   | Charger rated power          |
| `charger_model_<slave>`     | string  | —    | Charger model name           |
| `bluetooth_name_<slave>`    | string  | —    | BLE advertise name           |
| `phase_a_voltage_<slave>`   | numeric | V    | Phase A voltage              |
| `phase_b_voltage_<slave>`   | numeric | V    | Phase B voltage              |
| `phase_c_voltage_<slave>`   | numeric | V    | Phase C voltage              |
| `total_energy_<slave>`      | numeric | kWh  | Total energy delivered       |
| `charger_temp_<slave>`      | numeric | °C   | Charger temperature          |

---

## 🐞 Troubleshooting

* Verify charger accessibility on the Modbus TCP host/port.
* Check logs under `\[custom_components.huawei_emma_charger.*\]` for errors.
* If used alongside `huawei_solar`, run a **Modbus proxy** (e.g. `modbus-proxy`, `socat`) to multiplex connections.

---

## 🚧 TODO

* **Integration reload** currently does not re-discover sub-devices on reload.
  Expect a fix in an upcoming release.

---

## 🤝 Contributing & Support

Report issues or contribute at the GitHub repo:
[https://github.com/wookydo/huawei\_emma\_charger](https://github.com/wookydo/huawei_emma_charger)

Pull requests welcome!

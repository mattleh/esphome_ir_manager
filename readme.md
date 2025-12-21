# ESPHome IR Manager

A professional Home Assistant integration designed to bridge the gap between ESPHome IR receivers and transmitters. It allows you to capture NEC infrared codes, store them in a persistent library with custom names, and send them back through any ESPHome transmitter in your network.

## Features
- **Effortless Capture:** Monitors ESPHome text sensors for NEC signals.
- **Smart History:** Automatically maintains a list of the last 10 unique codes received.
- **Persistent Library:** Save codes to a JSON file (`/config/esphome_ir_codes.json`) so they survive restarts.
- **Dynamic Repeats:** Define how many times a signal should be repeated per command.
- **Localized UI:** Fully English interface with translation support.

---

## ESPHome Device Configuration

To use this integration, your ESPHome devices must be configured to handle the NEC protocol and expose a service to Home Assistant.

### 1. The Receiver (Capture Device)
The receiver should publish the NEC data to a `text_sensor` in the format `ADDR:XXXX|CMD:XXXX`.



```yaml
remote_receiver:
  pin: 
    number: D1
    inverted: True
  tolerance: 25%
  filter: 50us
  id: wz_receiver
  dump:
    - nec
  on_nec:
    then:
      - text_sensor.template.publish:
          id: ir_capture_sensor
          state: !lambda |-
            return str_sprintf("ADDR:%04X|CMD:%04X", x.address, x.command);

text_sensor:
  - platform: template
    name: "IR Capture Sensor"
    id: ir_capture_sensor
    icon: "mdi:remote-import"

remote_transmitter:
  pin: 
    number: D2 # Adjust to your specific GPIO pin
  carrier_duty_cycle: 50%

api:
  services:
    - service: send_ir_code_nec
      variables:
        address: int
        command: int
        repeats: int
      then:
        - remote_transmitter.transmit_nec:
            address: !lambda 'return address;'
            command: !lambda 'return command;'
            repeat: 
              times: !lambda 'return repeats;'
```

### How to Use
Step 1: Capture
Point your physical remote at the ESPHome receiver and press a button. The code will appear in the History Manager (found in the attributes of esphome_ir_manager.history_manager).

### Step 2: Save
Call the esphome_ir_manager.save_code service. Pick the captured code from the dropdown, provide a name (e.g., "TV Power"), and set your desired repeat count.

### Step 3: Send
Call the esphome_ir_manager.send_code service. Select your saved command and choose the esphome.your_device_send_ir_code_nec service as the target action.

### Technical Details
Protocol: Optimized for the NEC protocol.

Storage: Data is saved in esphome_ir_codes.json in your /config/ folder.

Requirements: The recorder integration must be active for the history to persist across UI refreshes.
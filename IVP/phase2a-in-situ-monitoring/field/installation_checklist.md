# Field Geotechnical Installation & Safety Protocol (Phase 2A)

> **Safety Priority:** Under no circumstances may field crews remain on or below an actively moving or breached slope mass during Warning or Critical states.

## 1. Pre-Deployment Verification
- [ ] Site mechanism confirmed by Engineering Geologist (Deep-seated, shallow, or rock slope).
- [ ] Landowner access permissions and civil authority work permits filed.
- [ ] Stable reference monument location surveyed outside predicted movement envelope.
- [ ] Cellular signal test completed; satellite backup terminal verified.
- [ ] Solar and battery sizing validated for minimum 14 consecutive overcast days.

## 2. Sensor Placement & As-Built Specifications
- [ ] **Stable Base:** GNSS reference station anchored to competent bedrock outside the unstable slope.
- [ ] **Moving Mass Array:** Minimum 2 independent instruments measuring primary movement axis (e.g., GNSS rover + wire extensometer across tension scarp).
- [ ] **Piezometers:** Installed in sealed borehole with sand pack across shear zone; non-vented sensors paired with barometric reference logger.
- [ ] **Extensometers:** Tension wire free of vegetation entanglements; thermal compensation thermistor attached.
- [ ] **Rain Gauge:** Levelled, wind-shielded, clear of canopy drip line.

## 3. Telemetry & Go-Live Gates
- [ ] End-to-end MQTT communication verified via TLS with unique client certificates.
- [ ] Monotonic sequence numbers and timestamp sync from GNSS verified.
- [ ] Local SD/Flash storage validated with capacity for $\ge 30$ days of offline back-fill buffering.
- [ ] Minimum 2-week baseline period scheduled to establish empirical noise floor ($\sigma$).
- [ ] Named site geotechnical owner and maintenance engineer assigned in site records.

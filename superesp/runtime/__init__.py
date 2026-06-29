"""superesp.runtime — the on-device "OS": read all ESP32 inputs, route, classify.

The runtime is what makes Atome the device's supervisor instead of a text
generator. It (1) continuously runs the OS head on fused chip telemetry to
track device health, (2) routes each sensor frame to the right applied head by
modality, and (3) applies abstention so the device stays quiet when unsure.
The C mirror lives in c_engine/superesp/superesp_os.c.
"""

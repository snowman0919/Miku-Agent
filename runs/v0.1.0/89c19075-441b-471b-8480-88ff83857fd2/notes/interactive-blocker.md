# Interactive track blocker

Offline BF16 mitigation succeeded, but the pinned NVIDIA interactive path
requires at least 80 GB VRAM, Docker Engine, and NVIDIA Container Toolkit.
This 32 GB RTX 5090 host does not satisfy those prerequisites, so loopback
streaming, TTFA, interruption, reconnect, and the 30-minute soak are not
measurable without changing hardware and host-wide runtime configuration.

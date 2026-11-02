# UDP Topology & Port 5053

- 5053/udp (default of `settings.node_listener_port`) is a **shared
  broadcast port** — multiple services on the LAN co-listen on it.
  Seeing 5053/udp already bound (`ss` output) is expected shared-listener
  behavior, NOT a port conflict. Don't change the port, add SO_REUSEADDR,
  or kill the other listener.
- Prod compose (`docker-compose.prod.yml`, api + scanner services) runs
  `network_mode: host` **on purpose** — host networking is what lets the
  container hear UDP broadcasts; a bridge network breaks broadcast
  reception. Don't switch to bridge networking.
- Send path: `comm.send(msg)` (`app/services/comm.py`) — module-global UDP
  socket (SO_BROADCAST enabled) + module-global `address`. Callers set
  `comm.address = (host, port)` before `send()`; unset → raises
  `Exception('Set address')`. `sendto` targets a specific node
  (`settings.node_listener`) or a broadcast address.
- Receive path: `device_scaner.py` runs `message_listener` `Server(
  port=node_listener_port, ip_address="0.0.0.0")` with a `MessageHandler`.
  The FastAPI app does NOT host a listener.

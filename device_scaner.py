from message_listener.server import Server
import node_manager.service.comm as comm



comm.address = (config.get("general.ip"), int(config.get("general.port")))
# starts a listener thread
serverSensor = Server()
serverSensor.add_handler('message_handler', MessageHandler())
serverSensor.start()
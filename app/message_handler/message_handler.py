from message_listener.abstract.handler_interface import \
    Handler as HandlerInterface


class MessageHandler(HandlerInterface):
    def handle(self, message):
        # print(message)
        if message is not None:
            name = message['node']
            if isinstance(message['chip_id'], int):
                _id = str(message['chip_id'])
            else:
                _id = message['chip_id']

            print(message)

            # adapt later
            # if message['event'] == 'system.pong':
            #     if not node:
            #         node = db.query(NodeModel).filter(NodeModel.node_id == _id).first()
            #     if node:
            #         node.node_system = message['parameters']
            #         db.commit()
            #
            # if message['event'] == 'system.microplate.hash':
            #     if not node:
            #         node = db.query(NodeModel).filter(NodeModel.node_id == _id).first()
            #     if node:
            #         node.node_micropython_hash = message['parameters']
            #         db.commit()
            #
            # if message['event'] == 'system.userspace.hash':
            #     if not node:
            #         node = db.query(NodeModel).filter(NodeModel.node_id == _id).first()
            #     if node:
            #         node.node_userspace_hash = message['parameters']
            #         db.commit()

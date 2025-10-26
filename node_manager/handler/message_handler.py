from message_listener.abstract.handler_interface import \
    Handler as HandlerInterface
import node_manager.service.db_helper as db_helper
from node_manager.model.node import NodeModel


class MessageHandler(HandlerInterface):
    cache = []

    def handle(self, message):
        # print(message)
        if message is not None:
            name = message['node']
            if isinstance(message['chip_id'], int):
                _id = str(message['chip_id'])
            else:
                _id = message['chip_id']

            cache_key = name+":"+_id
            db = next(db_helper.get_db())
            node = None
            if db is None:
                return

            # add new if neccessary
            if cache_key not in self.cache:
                node = db.query(NodeModel).filter(NodeModel.node_name == name, NodeModel.node_id == _id).first()
                if node is None:
                    node = NodeModel(
                        node_name=name,
                        node_id=_id,
                        microplate_repository="",
                        userspace_repository="",
                    )
                    db.add(node)
                    db.commit()
                self.cache.append(cache_key)

            if message['event'] == 'system.pong':
                if not node:
                    node = db.query(NodeModel).filter(NodeModel.node_name == name, NodeModel.node_id == _id).first()
                node.node_system = message['parameters']
                db.commit()

            if message['event'] == 'system.microplate.hash':
                if not node:
                    node = db.query(NodeModel).filter(NodeModel.node_name == name, NodeModel.node_id == _id).first()
                node.node_micropython_hash = message['parameters']
                db.commit()

            if message['event'] == 'system.userspace.hash':
                if not node:
                    node = db.query(NodeModel).filter(NodeModel.node_name == name, NodeModel.node_id == _id).first()
                node.node_userspace_hash = message['parameters']
                db.commit()

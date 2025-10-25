import os.path
from sqlalchemy import Column, Integer, String, DateTime, func
from flask import Flask, request, jsonify, send_file
from flasgger import Swagger
from node_manager.model.node import NodeModel
from node_manager.model.microplate import MicroplateHash
from node_manager.model.userspace import UserspaceHash
from node_manager.model.node import NodeUpgrade
from sqlalchemy.ext.declarative import declarative_base
from functools import wraps
from node_manager.service.comm import send
import logging
import uuid

logger = logging.getLogger(__name__)
Base = declarative_base()
API_TOKEN = None


def require_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("X-API-Token")
        if token != API_TOKEN or API_TOKEN is None:
            return jsonify({"message": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def init_api(app, cfg, microplate):
    swagger = Swagger(app)
    import node_manager.service.db_helper as db_helper
    global API_TOKEN
    API_TOKEN = cfg.get("api_key")
    db_helper.cfg = cfg
    db_helper.Base = Base
    db_helper.check_and_create_tables()

    @app.route("/api/nodes/ping")
    @require_token
    def ping():
        """
        Executes a broadcast ping to all nodes.
        ---
        responses:
            204:
                description: No content
        """
        msg = {'event': "system.ping"}
        send(msg)

        return '', 204

    @app.route("/api/node/<int:node_id>/ping")
    @require_token
    def node_ping(node_id):
        """
        Executes a broadcast ping to a node.
        ---
        parameters:
          - name: node_id
            in: path
            description: ID of the node to ping.
            required: true
            type: integer
        responses:
            204:
                description: No content
            404:
                description: Node not found
        """
        try:
            db = next(db_helper.get_db())
            node = db.query(NodeModel).get(node_id)
            if node is None:
                return '', 404
            msg = {'event': "system.ping", "targets": [node.node_name]}
            send(msg)
            return '', 204

        except Exception as e:
            print(f"Error pinging node {node_id}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/nodes")
    @require_token
    def nodes():
        """
        Get all nodes in the database.
        ---
        responses:
            200:
                description: List of nodes.
                schema:
                    type: array
                    items:
                        type: object
                        properties:
                            id:
                                type: integer
                                description: Node ID
                            node_name:
                                type: string
                                description: Name of the node
                            node_id:
                                type: string
                                description: Unique node identifier
                            node_system:
                                type: object
                                description: Node system information
                            node_micropython_hash:
                                type: object
                                description: MicroPython hash
                            node_userspace_hash:
                                type: object
                                description: User space hash
                            updated_at:
                                type: string
                                format: date-time
                                description: Last updated timestamp
                            created_at:
                                type: string
                                format: date-time
                                description: Creation timestamp
                            microplate_diff:
                                type: object
                                description: Difference hashes
                            microplate_repository:
                                type: string
                                description: Microplate repository name
                            userspace_repository:
                                type: string
                                description: Userspace repository name
                            userspace_diff:
                                type: object
                                description: Difference hashes for userspace
        """
        try:
            db = next(db_helper.get_db())
            nodes_list = db.query(NodeModel).all()
            nodes_data = []
            for node in nodes_list:
                node_data = {
                    "id": node.id,
                    "node_name": node.node_name,
                    "node_id": node.node_id,
                    "node_system": node.node_system,
                    "node_micropython_hash": node.node_micropython_hash,
                    "node_userspace_hash": node.node_userspace_hash,
                    "updated_at": str(node.updated_at),
                    "created_at": str(node.created_at),
                    "microplate_diff": microplate.get_microplate_diff_hashes(
                        node.node_micropython_hash,
                        node.microplate_repository
                    ),
                    "microplate_repository": node.microplate_repository,
                    "userspace_repository": node.userspace_repository,
                    "userspace_diff": microplate.get_userspace_diff_hashes(
                        node.node_userspace_hash,
                        node.userspace_repository
                    ),
                }
                nodes_data.append(node_data)
            return jsonify(nodes_data)
        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
            return jsonify({"error": str(e)}), 500

    ##########################
    # MICROPLATE ROUTES
    ##########################
    @app.route("/api/nodes/microplate/hash/scan")
    @require_token
    def hash_microplate():
        """
        Send broadcast with microplate hash recalculation to all nodes.
        ---
        responses:
           204:
                description: No content
        """
        msg = {'event': "system.microplate.get_hash"}
        send(msg)

        return '', 204

    @app.route("/api/node/<int:node_id>/microplate/hash/scan")
    @require_token
    def node_hash_microplate(node_id):
        """
        Send broadcast with microplate hash recalculation to a specific node.
        ---
        parameters:
            - name: node_id
              in: path
              required: true
              type: integer
              description: ID of the node to send the broadcast to.
        responses:
           204:
                description: No content
           404:
                description: Node not found

        """
        try:
            db = next(db_helper.get_db())
            node = db.query(NodeModel).get(node_id)
            if node is None:
                return '', 404
            msg = {'event': "system.microplate.get_hash", "targets": [node.node_name]}
            send(msg)
            return '', 204
        except Exception as e:
            print(f"Error pinging node {node_id}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/node/<int:node_id>/microplate/repository", methods=['POST'])
    @require_token
    def node_assign_microplate_repository(node_id):
        """
        Assign a microplate repository to the node.
        ---
        parameters:
            - name: node_id
              in: path
              required: true
              type: integer
              description: ID of the node to assign the microplate repository to.
            - name: body
              in: body
              required: true
              schema:
                id: MicroplateRepository
                required:
                    - name
                properties:
                    name:
                        type: string
                        description: Name of the microplate repository to assign
                        example: "aaa"
        responses:
            204:
                description: Microplate repository assigned successfully.
            500:
                description: Internal server error.
            404:
                description: Node not found.

        """
        db = next(db_helper.get_db())
        node = db.query(NodeModel).get(node_id)
        if node is None:
            return '', 404
        node.microplate_repository = request.json.get('name')
        db.commit()
        return '', 204

    @app.route("/api/microplate/repositories", methods=['GET'])
    @require_token
    def microplate_repos():
        """Fetch all microplate repositories
        ---
        responses:
            200:
                description: List of microplate repositories
                schema:
                    type: array
                    items:
                        type: string
        """
        repos = microplate.get_microplate_repositories()

        return jsonify(repos)

    @app.route("/api/microplate/<repository>/hash/scan", methods=['POST'])
    @require_token
    def microplate_hash_scan(repository):
        """
        Scans given repository for microplate hashes and saves them to the database.
        ---
        parameters:
           - name: repository
             in: path
             type: string
        responses:
           200:
              description: Successfully saved hashes
        """
        hashes = microplate.scan_directory(os.path.join(repository, '_microplate'))
        microplate.save_microplate_hashes(hashes, repository)

        return jsonify(None)

    @app.route("/api/microplate/<repository>/files", methods=['GET'])
    @require_token
    def microplate_repository_file_list(repository):
        """
        Get all microplate files and their hashes for a given repository.
        ---
        parameters:
           - name: repository
             in: path
             type: string
        responses:
           200:
                description: List of microplate files and their hashes
                schema:
                    type: array
                    items:
                        type: object
                        properties:
                            id:
                                type: integer
                                description: id of the microplate file
                            name:
                                type: string
                                description: Name of the file
                            hash:
                                type: string
                                description: hash of the file
                            updated_at:
                                type: string
                                description: date and time when the file was last modified
                            created_at:
                                type: string
                                description: date and time when the file was created
        """
        try:
            db = next(db_helper.get_db())
            _list = db.query(MicroplateHash).filter(MicroplateHash.repository==repository).order_by(MicroplateHash.name).all()
            data = []
            for item in _list:
                data.append({
                    "id": item.id,
                    "name": item.name,
                    "hash": item.hash,
                    "repository": item.repository,
                    "updated_at": str(item.updatedAt),
                    "created_at": str(item.createdAt),
                })
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
            return jsonify({"error": str(e)}), 500

    ##########################
    # USERSPACE ROUTES
    ##########################
    @app.route("/api/node/<int:node_id>/userspace/repository", methods=['POST'])
    @require_token
    def node_assign_userspace_repository(node_id):
        """
        Assign an userspace repository to the node.
        ---
        parameters:
            - name: node_id
              in: path
              required: true
              type: integer
              description: ID of the node to assign the microplate repository to.
            - name: body
              in: body
              required: true
              schema:
                id: UserspaceRepository
                required:
                    - name
                properties:
                    name:
                        type: string
                        description: Name of the userspace repository to assign
                        example: "aaa"
        responses:
            204:
                description: Userspace repository assigned successfully.
            500:
                description: Internal server error.
            404:
                description: Node not found.

        """
        db = next(db_helper.get_db())
        node = db.query(NodeModel).get(node_id)
        if node is None:
            return '', 404
        node.userspace_repository = request.json.get('name')
        db.commit()
        return '', 204

    @app.route("/api/nodes/userspace/hash/scan")
    @require_token
    def hash_userspace():
        """Broadcast the message for user space to all nodes in the network.
        ----
        response:
            204:
                description: Hash of the userspace broadcast successfully.
        """
        msg = {'event': "system.userspace.get_hash"}
        send(msg)

        return '', 204

    @app.route("/api/node/<int:node_id>/userspace/hash/scan")
    @require_token
    def node_userspace_hash_scan(node_id):
        """Broadcast the message for user space hash to the specified node.
        ----
        parameters:
           - name: node_id
             in: path
             type: integer
             required: true
        response:
            204:
                description: Hash of the userspace broadcast successfully.
            404:
                description: Node not found.
        """
        try:
            db = next(db_helper.get_db())
            node = db.query(NodeModel).get(node_id)
            if node is None:
                return '', 404
            msg = {'event': "system.userspace.get_hash", "targets": [node.node_name]}
            send(msg)
            return '', 204
        except Exception as e:
            print(f"Error pinging node {node_id}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/userspace/repositories", methods=['GET'])
    @require_token
    def userspace_repos():
        """Fetch all userspace repositories
        ---
        responses:
            200:
                description: List of userspace repositories
                schema:
                    type: array
                    items:
                        type: string
        """
        repos = microplate.get_userspace_repositories()

        return jsonify(repos)

    @app.route("/api/userspace/<repository>/hash/scan", methods=['POST'])
    @require_token
    def userspace_hash_scan(repository):
        """
        Scans given repository for userspace hashes and saves them to the database.
        ---
        parameters:
           - name: repository
             in: path
             type: string
        responses:
           200:
              description: Successfully saved hashes
        """
        hashes = microplate.scan_directory(os.path.join(repository, '_userspace'))
        microplate.save_userspace_hashes(hashes, repository)

        return jsonify(None)

    @app.route("/api/userspace/<repository>/files", methods=['GET'])
    @require_token
    def userspace_repository_file_list(repository):
        """
        Get all userspace files and their hashes for a given repository.
        ---
        parameters:
           - name: repository
             in: path
             type: string
        responses:
           200:
                description: List of userspace files and their hashes
                schema:
                    type: array
                    items:
                        type: object
                        properties:
                            id:
                                type: integer
                                description: id of the microplate file
                            name:
                                type: string
                                description: Name of the file
                            hash:
                                type: string
                                description: hash of the file
                            updated_at:
                                type: string
                                description: date and time when the file was last modified
                            created_at:
                                type: string
                                description: date and time when the file was created
        """
        try:
            db = next(db_helper.get_db())
            _list = db.query(UserspaceHash).filter(UserspaceHash.repository==repository).order_by(UserspaceHash.name).all()
            data = []
            for item in _list:
                data.append({
                    "id": item.id,
                    "name": item.name,
                    "hash": item.hash,
                    "repository": item.repository,
                    "updated_at": str(item.updatedAt),
                    "created_at": str(item.createdAt),
                })
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/node/<int:node_id>/userspace/upgrade", methods=["POST"])
    @require_token
    def send_upgrade_userspace_message(node_id):
        """
        Send a message with upgrade request to the specified node.
        ---
        parameters:
            - name: node_id
            in: path
            type: integer
              required: true
               description: The ID of the node to upgrade
        responses:
            200:
                description: Message sent successfully
            404:
                description: Node not found
        """
        try:
            db = next(db_helper.get_db())
            node = db.query(NodeModel).get(node_id)
            if not node:
                return jsonify({"error": "Node not found"}), 404

            token = uuid.uuid4()
            upgrade_node = NodeUpgrade(
                token=token,
                type="userspace",
                node_id=node.id,
            )
            db.add(upgrade_node)
            db.commit()

            diff = microplate.get_userspace_diff_hashes(
                node.node_userspace_hash,
                node.userspace_repository
            )
            msg = {'event': "system.userspace.upgrade",
                   "targets": [node.node_name],
                   "parameters": {
                       'type': 'userfiles',
                       "files": diff,
                       "base_url": f"{cfg['base_url']}:{cfg['port']}/api/upgrade/{token}"
                   }
               }
            print(msg)
            send(msg)

            return '', 204
        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
            return jsonify({"error": str(e)}), 500

    ##########################
    # UPDATE NODES ROUTES
    ##########################
    @app.route("/api/upgrade/<uuid>/get/<filename>", methods=["GET"])
    def send_userspace_file(uuid, filename):
        db = next(db_helper.get_db())
        upgrade = db.query(NodeUpgrade).filter(NodeUpgrade.token==uuid).first()
        if not upgrade:
            return jsonify({"error": "Upgrade not found"}), 404

        node = db.query(NodeModel).filter(NodeModel.id==upgrade.node_id).first()
        if not node:
            return jsonify({"error": "Node not found"}), 404

        if upgrade.type == "userspace":
            filepath = os.path.join(microplate.get_repository_path(node.userspace_repository), '_userspace', filename)
            return send_file(filepath, as_attachment=True)
        elif upgrade.type == "microplate":
            filepath = os.path.join(microplate.get_repository_path(node.microplate_repository), '_microplate', filename)
            return send_file(filepath, as_attachment=True)

        return jsonify({"error": "Invalid upgrade type"}), 400

    @app.route("/api/upgrade/<uuid>/validate/<filename>", methods=["POST"])
    def validate_userspace_file(uuid, filename):
        db = next(db_helper.get_db())
        upgrade = db.query(NodeUpgrade).filter(NodeUpgrade.token==uuid).first()
        if not upgrade:
            return jsonify({"error": "Upgrade not found"}), 404
        node = db.query(NodeModel).filter(NodeModel.id==upgrade.node_id).first()
        if not node:
            return jsonify({"error": "Node not found"}), 404
        _hash = request.json.get('hash')
        if upgrade.type == "userspace":
            _file = db.query(UserspaceHash).filter(UserspaceHash.repository==node.userspace_repository).filter(UserspaceHash.name==filename).first()
            if not node:
                return jsonify({"error": "Hash not found"}), 404
            if _file.hash == _hash:
                return jsonify(None), 200

        return jsonify({"error": "Hash mismatch"}), 400

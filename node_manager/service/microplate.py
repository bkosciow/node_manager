import sys
import os
import logging
from node_manager.service.hasher import file_hash
import node_manager.service.db_helper as db_helper
from node_manager.model.microplate import MicroplateHash
from node_manager.model.userspace import UserspaceHash
from datetime import datetime

logger = logging.getLogger(__name__)


class Microplate:
    def __init__(self, cfg):
        self.cfg = cfg
        if cfg['path'][0] != '/':
            frame = sys._getframe(1)
            server_path = os.path.abspath(frame.f_code.co_filename)
            self.path = os.path.join(os.path.dirname(server_path), cfg['path'])
        else:
            self.path = cfg['path']
        if not os.path.exists(self.path):
            logger.error("""Path %d does not exists"""% (self.path))

    def get_microplate_repositories(self):
        return self._get_dir_list('_microplate')

    def get_userspace_repositories(self):
        return self._get_dir_list('_userspace')

    def _get_dir_list(self, subdir):
        data = []
        try:
            for filename in os.listdir(self.path):
                dirpath = os.path.join(self.path, filename, subdir)
                if os.path.isdir(dirpath):
                    data.append(filename)

        except Exception as e:
            print(f"Error scanning directory '{self.path}': {e}")

        return sorted(data)

    def get_repository_path(self, repository_name):
        return os.path.join(self.path, repository_name)

    def scan_directory(self, repository):
        hashes = {}
        base_path = os.path.join(self.path, repository)
        try:
            for filename in os.listdir(base_path):
                if filename == '.gitkeep':
                    continue
                filepath = os.path.join(base_path, filename)
                if os.path.isfile(filepath):
                    hashes[filename] = file_hash(filepath)

        except Exception as e:
            print(f"Error scanning directory '{base_path}': {e}")

        return hashes

    def save_microplate_hashes(self, hashes, repository):
        db = next(db_helper.get_db())
        try:
            for filename, hash_value in hashes.items():
                existing_hash = db.query(MicroplateHash).filter(MicroplateHash.repository==repository).filter(MicroplateHash.name == filename).first()

                if existing_hash:
                    existing_hash.hash = hash_value
                    existing_hash.updatedAt = datetime.now()
                else:
                    new_hash = MicroplateHash(
                        name=filename,
                        hash=hash_value,
                        repository=repository,
                        createdAt=datetime.now(),
                        updatedAt=datetime.now()
                    )
                    db.add(new_hash)

            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error saving/updating hashes to database: {e}")
        finally:
            db.close()

    def save_userspace_hashes(self, hashes, repository):
        db = next(db_helper.get_db())
        try:
            for filename, hash_value in hashes.items():
                existing_hash = db.query(UserspaceHash).filter(UserspaceHash.repository==repository).filter(UserspaceHash.name == filename).first()

                if existing_hash:
                    existing_hash.hash = hash_value
                    existing_hash.updatedAt = datetime.now()
                else:
                    new_hash = UserspaceHash(
                        name=filename,
                        hash=hash_value,
                        repository=repository,
                        createdAt=datetime.now(),
                        updatedAt=datetime.now()
                    )
                    db.add(new_hash)

            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error saving/updating hashes to database: {e}")
        finally:
            db.close()

    def get_microplate_diff_hashes(self, hashes, repository):
        if not hashes:
            return []
        db = next(db_helper.get_db())
        _list = db.query(MicroplateHash).filter(MicroplateHash.repository == repository).order_by(
            MicroplateHash.name).all()
        return self._return_hash_diff(_list, hashes)

    def get_userspace_diff_hashes(self, hashes, repository):
        if not hashes:
            return []
        db = next(db_helper.get_db())
        _list = db.query(UserspaceHash).filter(UserspaceHash.repository == repository).order_by(
            UserspaceHash.name).all()
        return self._return_hash_diff(_list, hashes)

    def _return_hash_diff(self, _list, hashes):
        db_hashes = {item.name: item.hash for item in _list}
        diff = []
        for filename, db_hash in db_hashes.items():
            if filename not in hashes or hashes[filename] != db_hash:
                diff.append(filename)
        return diff

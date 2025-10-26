from node_manager.service.config import Config
import logging
from node_manager.service.microplate import Microplate
import os
import node_manager.service.db_helper as db_helper
from node_manager.model.microplate import MicroplateHash
from node_manager.model.userspace import UserspaceHash
import datetime
from node_manager.service.hasher import file_hash


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

config = Config('config.ini')
db_helper.cfg = config['api']


def scan_files(base_dir, repo, subdir):
    try:
        dirpath = os.path.join(base_dir, repo, subdir)
        if os.path.isdir(dirpath):
            for _file in os.listdir(dirpath):
                if _file == '.gitkeep':
                    continue
                yield os.path.join(dirpath, _file)
    except Exception as e:
        print(f"Error scanning directory '{repo}': {e}")


def validate_files(db, repos, subdir):
    for repo in repos:
        for _file in scan_files(config.get('microplate.path'), repo, subdir):
            stat = os.stat(_file)
            file_datetime = datetime.datetime.fromtimestamp(stat.st_mtime)
            if subdir == '_userspace':
                item = db.query(UserspaceHash).filter(UserspaceHash.repository==repo, UserspaceHash.name==os.path.basename(_file)).first()
            else:
                item = db.query(MicroplateHash).filter(MicroplateHash.repository==repo, MicroplateHash.name==os.path.basename(_file)).first()
            if item is None:
                logger.info(f"New file detected: {_file}")
                item = MicroplateHash(
                    name=os.path.basename(_file),
                    hash=file_hash(_file),
                    repository=repo,
                    createdAt=datetime.datetime.now(),
                    updatedAt=datetime.datetime.now()
                )
                db.add(item)
                db.commit()
            elif file_datetime > item.updatedAt:
                logger.info(f"New hash: {_file}")
                item.hash = file_hash(_file)
                item.updatedAt = datetime.datetime.now()
                db.commit()


def scan():
    microplate = Microplate(config['microplate'])
    db = next(db_helper.get_db())
    repos = microplate.get_microplate_repositories()
    validate_files(db, repos, "_microplate")

    repos = microplate.get_userspace_repositories()
    validate_files(db, repos, "_userspace")
    db.close()


if __name__ == "__main__":
    logger.info("Starting repo scanner")
    scan()

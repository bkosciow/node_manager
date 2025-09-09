from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MicroplateHash(Base):
    __tablename__ = 'microplate_hashes'

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)  # Name of the file
    hash = Column(String(256), nullable=False)  # SHA256 Hash
    repository = Column(String(512), nullable=False)
    createdAt = Column(DateTime, nullable=False)
    updatedAt = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<FileHash(id={self.id}, name='{self.name}', hash='{self.hash[:8]}...')>"

from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Float, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
import time

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

def current_time_millis():
    return int(time.time())

class Project(Base):
    __tablename__ = 'projects'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    north_star_hypothesis_id = Column(String, nullable=True) # Can't be FK yet as circular dep potential
    status = Column(String, default="active")
    members = Column(JSON, default=list) # List of strings
    layout_mode = Column(String, default="breadthfirst")
    created_at = Column(Integer, default=current_time_millis)

    # Relationships
    hypotheses = relationship("Hypothesis", back_populates="project", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="project", cascade="all, delete-orphan")

class Hypothesis(Base):
    __tablename__ = 'hypotheses'

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey('projects.id'))
    parent_id = Column(String, ForeignKey('hypotheses.id'), nullable=True)
    statement = Column(Text, nullable=False)
    status = Column(String, default="open")
    metrics = Column(JSON, default=list)
    position = Column(JSON, default=dict) # {x: float, y: float}
    created_at = Column(Integer, default=current_time_millis)

    # Relationships
    project = relationship("Project", back_populates="hypotheses")
    parent = relationship("Hypothesis", remote_side=[id], backref="children_nodes")
    updates = relationship("Update", back_populates="hypothesis", cascade="all, delete-orphan")

    # Helper to mimic the old 'children' list property
    @property
    def children(self):
        return [c.id for c in self.children_nodes]

class Update(Base):
    __tablename__ = 'updates'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    hypothesis_id = Column(String, ForeignKey('hypotheses.id'))
    author = Column(String, default="")
    date = Column(Integer, default=current_time_millis)
    content = Column(Text, default="")
    metrics = Column(JSON, default=dict)
    evidence_status = Column(String, default="neutral")

    # Relationships
    hypothesis = relationship("Hypothesis", back_populates="updates")

class Snapshot(Base):
    __tablename__ = 'snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey('projects.id'))
    timestamp = Column(Integer)
    data = Column(JSON) # Full project state dump
    
    # Relationships
    project = relationship("Project", back_populates="snapshots")


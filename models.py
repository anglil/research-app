
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import time
import uuid

def generate_id():
    return str(uuid.uuid4())

def timestamp_now():
    return int(time.time())

@dataclass
class Update:
    id: str = field(default_factory=generate_id)
    hypothesis_id: str = ""
    author: str = ""
    date: int = field(default_factory=timestamp_now)
    content: str = ""
    metrics: Dict[str, float] = field(default_factory=dict) # e.g. {"accuracy": 0.85}
    evidence_status: str = "neutral" # supporting, refuting, neutral
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Hypothesis:
    id: str = field(default_factory=generate_id)
    project_id: str = ""
    parent_id: Optional[str] = None
    statement: str = ""
    status: str = "open" # open, tested, proven, disproven
    metrics: List[Dict] = field(default_factory=list) # e.g. [{"name": "accuracy", "target": 0.9}]
    updates: List[Update] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    position: Dict[str, float] = field(default_factory=dict) # x, y coordinates
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Project:
    id: str = field(default_factory=generate_id)
    title: str = ""
    north_star_hypothesis_id: str = ""
    status: str = "active"
    members: List[str] = field(default_factory=list)
    layout_mode: str = "breadthfirst" # breadthfirst, circle, grid, random, concentric, dagre

    def to_dict(self):
        return asdict(self)

from database import get_db, init_db
from models_sql import Project, Hypothesis, Update, Snapshot
from sqlalchemy.orm import Session
import time
import json

# Ensure DB tables exist
init_db()

def _get_session():
    return next(get_db())

# --- PROJECTS ---

def create_project(title: str, north_star_statement: str):
    db: Session = _get_session()
    
    # 1. Create Project
    new_project = Project(title=title)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    # 2. Create North Star Hypothesis
    ns_hypothesis = Hypothesis(
        project_id=new_project.id,
        statement=north_star_statement,
        position={"x": 0, "y": 0}
    )
    db.add(ns_hypothesis)
    db.commit()
    db.refresh(ns_hypothesis)
    
    # 3. Link North Star to Project
    new_project.north_star_hypothesis_id = ns_hypothesis.id
    db.commit()
    
    # 4. Initial Snapshot
    save_snapshot(new_project.id)
    return new_project

def get_projects():
    db = _get_session()
    return db.query(Project).all()

def save_project(project: Project):
    db = _get_session()
    # If detached, merge
    db.merge(project)
    db.commit()

# --- HYPOTHESES ---

def get_hypothesis(h_id: str, snapshot_data=None):
    if snapshot_data:
        # Fallback to reading from dict if snapshot provided
        from models import Hypothesis as H_Dataclass, Update as U_Dataclass
        if h_id in snapshot_data:
            data = snapshot_data[h_id]
            # Convert dict updates to Dataclass updates
            raw_updates = data.get('updates', [])
            clean_updates = [U_Dataclass(**u) for u in raw_updates]
            data['updates'] = clean_updates
            return H_Dataclass(**data)
        return None

    db = _get_session()
    return db.query(Hypothesis).filter(Hypothesis.id == h_id).first()

def save_hypothesis(h, trigger_snapshot=True):
    db = _get_session()
    db.merge(h)
    db.commit()
    
    if trigger_snapshot and h.project_id:
        save_snapshot(h.project_id)

def add_subhypothesis(parent_id: str, statement: str):
    db = _get_session()
    parent = db.query(Hypothesis).filter(Hypothesis.id == parent_id).first()
    if not parent: return
    
    child = Hypothesis(
        project_id=parent.project_id,
        parent_id=parent.id,
        statement=statement,
        position={"x": 0, "y": 0}
    )
    db.add(child)
    db.commit()
    
    save_snapshot(parent.project_id)

def delete_hypothesis(h_id: str):
    db = _get_session()
    h = db.query(Hypothesis).filter(Hypothesis.id == h_id).first()
    if not h: return
    
    pid = h.project_id
    
    # If root/north star, prevent? Or allow and break project?
    # Logic: Delete h and all children (cascade handles children updates via ORM if strict, 
    # but self-referential cascade is tricky, SQLAlchemy usually needs 'cascade="all, delete-orphan"' on relationship)
    
    db.delete(h)
    db.commit()
    
    save_snapshot(pid)

def reverse_relationship(child_id: str):
    db = _get_session()
    child = db.query(Hypothesis).filter(Hypothesis.id == child_id).first()
    if not child or not child.parent_id: return

    parent = db.query(Hypothesis).filter(Hypothesis.id == child.parent_id).first()
    if not parent: return
    
    grandparent_id = parent.parent_id
    
    # 1. Parent becomes child of Child
    parent.parent_id = child.id
    
    # 2. Child adopts Grandparent
    child.parent_id = grandparent_id
    
    # 3. Update North Star if needed
    if not grandparent_id:
        proj = db.query(Project).filter(Project.id == parent.project_id).first()
        if proj and proj.north_star_hypothesis_id == parent.id:
            proj.north_star_hypothesis_id = child.id
            db.merge(proj)

    db.commit()
    save_snapshot(child.project_id)

# --- SCIENTIFIC LOG ---

def add_update(h_id: str, author: str, content: str, metrics: dict, evidence_status: str):
    db = _get_session()
    up = Update(
        hypothesis_id=h_id,
        author=author,
        content=content,
        metrics=metrics,
        evidence_status=evidence_status
    )
    db.add(up)
    db.commit()
    
    # Update Status Logic
    h = db.query(Hypothesis).filter(Hypothesis.id == h_id).first()
    if h:
        if evidence_status == "supporting":
            h.status = "proven"
        elif evidence_status == "refuting":
            h.status = "disproven"
        elif evidence_status == "neutral" and h.status == "open":
            h.status = "tested"
        db.commit()

# --- SNAPSHOTS ---

def save_snapshot(project_id: str):
    db = _get_session()
    
    # Dump all hypotheses for this project to JSON
    hypotheses = db.query(Hypothesis).filter(Hypothesis.project_id == project_id).all()
    
    dump = {}
    for h in hypotheses:
        # Manual serialize to avoid recursion limits or circular deps
        h_dict = {
            "id": h.id,
            "project_id": h.project_id,
            "parent_id": h.parent_id,
            "statement": h.statement,
            "status": h.status,
            "metrics": h.metrics,
            "position": h.position,
            "children": [c.id for c in h.children_nodes],
            "updates": [
                {
                    "id": u.id,
                    "author": u.author,
                    "date": u.date,
                    "content": u.content,
                    "evidence_status": u.evidence_status
                } for u in h.updates
            ]
        }
        dump[h.id] = h_dict
        
    snap = Snapshot(
        project_id=project_id,
        timestamp=int(time.time()),
        data=dump
    )
    db.add(snap)
    db.commit()

def get_snapshots(project_id: str):
    db = _get_session()
    snaps = db.query(Snapshot).filter(Snapshot.project_id == project_id).order_by(Snapshot.timestamp.desc()).all()
    return [s.timestamp for s in snaps]

def load_snapshot_hypotheses(project_id: str, timestamp: int):
    db = _get_session()
    snap = db.query(Snapshot).filter(Snapshot.project_id == project_id, Snapshot.timestamp == timestamp).first()
    if snap:
        return snap.data
    return None

def undo_last_action(project_id: str):
    db = _get_session()
    snaps = db.query(Snapshot).filter(Snapshot.project_id == project_id).order_by(Snapshot.timestamp.desc()).limit(2).all()
    
    if len(snaps) < 2: return False
    
    target_data = snaps[1].data
    
    # Brutal Restore: Delete all current hyps for project and recreate from JSON
    # This is heavy but "safe" for consistency.
    db.query(Update).filter(Update.hypothesis.has(project_id=project_id)).delete(synchronize_session=False)
    db.query(Hypothesis).filter(Hypothesis.project_id == project_id).delete(synchronize_session=False)
    
    for h_id, h_data in target_data.items():
        # Recreate Hypothesis
        h = Hypothesis(
            id=h_id,
            project_id=h_data['project_id'],
            parent_id=h_data['parent_id'],
            statement=h_data['statement'],
            status=h_data['status'],
            metrics=h_data.get('metrics', []),
            position=h_data.get('position', {})
        )
        db.add(h)
        
        # Recreate Updates
        for u_data in h_data.get('updates', []):
            u = Update(
                id=u_data['id'],
                hypothesis_id=h_id,
                author=u_data['author'],
                date=u_data['date'],
                content=u_data['content'],
                evidence_status=u_data['evidence_status']
            )
            db.add(u)
            
    # Delete the "bad" latest snapshot
    db.delete(snaps[0])
    db.commit()
    return True

# --- PEOPLE VIEW ---

def get_all_authors():
    db = _get_session()
    # Distinct authors
    # This is a bit rough with comma-sep strings, might need optimized query or Python process
    updates = db.query(Update).all()
    authors = set()
    for u in updates:
        if u.author:
             for a in u.author.replace(",", ";").split(";"):
                 authors.add(a.strip())
    return sorted(list(authors))

def get_updates_by_author(author_name: str):
    db = _get_session()
    updates = db.query(Update).all()
    results = []
    
    for u in updates:
        auths = [a.strip() for a in u.author.replace(",", ";").split(";")]
        if author_name in auths:
            results.append({
                "project_title": u.hypothesis.project.title,
                "hypothesis_statement": u.hypothesis.statement,
                "date": u.date,
                "content": u.content,
                "evidence": u.evidence_status
            })
    return sorted(results, key=lambda x: x['date'], reverse=True)


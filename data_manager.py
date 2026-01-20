import json
import os
import shutil
from typing import List, Dict, Optional
from models import Project, Hypothesis, Update
import dataclasses
import time

DATA_DIR = "data"
HISTORY_DIR = os.path.join(DATA_DIR, "history")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
HYPOTHESES_FILE = os.path.join(DATA_DIR, "hypotheses.json")

def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

_ensure_dir(DATA_DIR)
_ensure_dir(HISTORY_DIR)

def _load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as f:
        return json.load(f)

def _save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def save_snapshot(project_id: str):
    """Saves a timestamped copy of the current hypotheses state for a project."""
    # For MVP simplicity, we snapshot the ENTIRE hypotheses file. 
    # Real app would filter by project or use a database.
    timestamp = int(time.time())
    project_history_dir = os.path.join(HISTORY_DIR, project_id)
    _ensure_dir(project_history_dir)
    
    snapshot_path = os.path.join(project_history_dir, f"{timestamp}.json")
    shutil.copy(HYPOTHESES_FILE, snapshot_path)

def get_snapshots(project_id: str) -> List[int]:
    project_history_dir = os.path.join(HISTORY_DIR, project_id)
    if not os.path.exists(project_history_dir):
        return []
    files = os.listdir(project_history_dir)
    timestamps = []
    for f in files:
        if f.endswith(".json"):
            try:
                timestamps.append(int(f.replace(".json", "")))
            except:
                pass
    return sorted(timestamps, reverse=True)

def load_snapshot_hypotheses(project_id: str, timestamp: int) -> Dict:
    path = os.path.join(HISTORY_DIR, project_id, f"{timestamp}.json")
    return _load_json(path)

def get_projects() -> List[Project]:
    data = _load_json(PROJECTS_FILE)
    return [Project(**p) for p in data.values()]

def save_project(project: Project):
    data = _load_json(PROJECTS_FILE)
    data[project.id] = project.to_dict()
    _save_json(PROJECTS_FILE, data)

def get_hypothesis(h_id: str, snapshot_data: Optional[Dict] = None) -> Optional[Hypothesis]:
    data = snapshot_data if snapshot_data is not None else _load_json(HYPOTHESES_FILE)
    if h_id not in data:
        return None
    h_data = data[h_id]
    
    # Reconstruct updates list with Update objects
    raw_updates = h_data.get('updates', [])
    clean_updates = []
    for u in raw_updates:
        clean_updates.append(Update(**u))
    h_data['updates'] = clean_updates
    
    return Hypothesis(**h_data)

def save_hypothesis(hypothesis: Hypothesis, trigger_snapshot=True):
    data = _load_json(HYPOTHESES_FILE)
    h_dict = hypothesis.to_dict()
    data[hypothesis.id] = h_dict
    _save_json(HYPOTHESES_FILE, data)
    
    if trigger_snapshot and hypothesis.project_id:
        save_snapshot(hypothesis.project_id)

def create_project(title: str, north_star_statement: str):
    north_star = Hypothesis(statement=north_star_statement)
    project = Project(title=title, north_star_hypothesis_id=north_star.id)
    north_star.project_id = project.id
    
    save_hypothesis(north_star, trigger_snapshot=False)
    save_project(project)
    save_snapshot(project.id)
    return project

def add_subhypothesis(parent_id: str, statement: str):
    parent = get_hypothesis(parent_id)
    if not parent:
        return None
        
    child = Hypothesis(statement=statement, project_id=parent.project_id, parent_id=parent_id)
    save_hypothesis(child, trigger_snapshot=False) # Delay snapshot
    
    parent.children.append(child.id)
    save_hypothesis(parent, trigger_snapshot=True) # Snapshot once linked
    return child

def add_update(hypothesis_id: str, author: str, content: str, metrics: Dict, evidence: str):
    hypothesis = get_hypothesis(hypothesis_id)
    if not hypothesis:
        return
    
    if "," in author:
        authors_list = [a.strip() for a in author.split(",")]
        clean_author = ", ".join(authors_list)
    else:
        clean_author = author.strip()
        
    update = Update(hypothesis_id=hypothesis_id, author=clean_author, content=content, metrics=metrics, evidence_status=evidence)
    hypothesis.updates.append(update)
    save_hypothesis(hypothesis, trigger_snapshot=True)

def delete_hypothesis(hypothesis_id: str):
    h = get_hypothesis(hypothesis_id)
    if not h: return
    
    # Check if root (north star)
    # 1. Remove from parent's children list
    if h.parent_id:
        parent = get_hypothesis(h.parent_id)
        if parent and h.id in parent.children:
            parent.children.remove(h.id)
            save_hypothesis(parent, trigger_snapshot=False)
    
    # 2. Delete the node and its subtree (recursive)
    # Helper to collect all IDs to delete
    ids_to_delete = [h.id]
    queue = h.children[:]
    while queue:
        current_child_id = queue.pop(0)
        ids_to_delete.append(current_child_id)
        current_child = get_hypothesis(current_child_id)
        if current_child:
            queue.extend(current_child.children)
            
    # 3. Perform deletion
    hypotheses_data = _load_json(HYPOTHESES_FILE)
    for hid in ids_to_delete:
        if hid in hypotheses_data:
            del hypotheses_data[hid]
    _save_json(HYPOTHESES_FILE, hypotheses_data)
    
    # Snapshot after deletion (using project ID from the original node)
    if h.project_id:
        save_snapshot(h.project_id)

def reverse_relationship(child_id: str):
    """
    Reverses the edge between child and its parent.
    Child becomes Parent. Parent becomes Child.
    """
    child = get_hypothesis(child_id)
    if not child or not child.parent_id:
        return # Can't reverse if no parent (root)

    parent = get_hypothesis(child.parent_id)
    if not parent:
        return

    grandparent_id = parent.parent_id
    
    # 1. Update Grandparent (if exists) to point to Child instead of Parent
    if grandparent_id:
        grandparent = get_hypothesis(grandparent_id)
        if grandparent:
            if parent.id in grandparent.children:
                grandparent.children.remove(parent.id)
                grandparent.children.append(child.id)
                save_hypothesis(grandparent, trigger_snapshot=False)
    
    # Special: If Parent was North Star (no grandparent), Child becomes new North Star?
    # We might need to update Project record if so.
    if not grandparent_id and parent.project_id:
        projects = get_projects()
        for p in projects:
            if p.id == parent.project_id and p.north_star_hypothesis_id == parent.id:
                p.north_star_hypothesis_id = child.id
                save_project(p)
                break

    # 2. Update Parent
    # Remove child from parent's children
    if child.id in parent.children:
        parent.children.remove(child.id)
    # Parent now becomes child of Child
    parent.parent_id = child.id
    
    # 3. Update Child
    child.parent_id = grandparent_id
    # Add Parent to Child's children
    child.children.append(parent.id)
    
    # Save both
    save_hypothesis(parent, trigger_snapshot=False)
    save_hypothesis(child, trigger_snapshot=True)

def delete_edge_relationship(child_id: str):
    """
    Removes the link between a child and its parent.
    The child becomes a root node (orphaned from the tree).
    """
    child = get_hypothesis(child_id)
    if not child or not child.parent_id:
        return
        
    parent = get_hypothesis(child.parent_id)
    if parent:
        if child.id in parent.children:
            parent.children.remove(child.id)
            save_hypothesis(parent, trigger_snapshot=False)
            
    child.parent_id = None
    save_hypothesis(child, trigger_snapshot=True)

def get_all_authors():
    """Iterates all projects to find unique authors from updates."""
    authors = set()
    projects = get_projects()
    for p in projects:
        data = load_project_data(p.id)
        for h in data["hypotheses"].values():
            if h.updates:
                for u in h.updates:
                    if u.author:
                        # Handle comma-separated authors
                        for auth in u.author.replace(",", ";").split(";"):
                            clean_auth = auth.strip()
                            if clean_auth:
                                authors.add(clean_auth)
    return sorted(list(authors))

def get_updates_by_author(author_name: str):
    """Aggregates all updates by a specific author across all projects."""
    author_updates = []
    projects = get_projects()
    for p in projects:
        data = load_project_data(p.id)
        for h in data["hypotheses"].values():
            if h.updates:
                for u in h.updates:
                    # Check if author matches (handling multiple authors)
                    current_authors = [a.strip() for a in u.author.replace(",", ";").split(";")]
                    if author_name in current_authors:
                        author_updates.append({
                            "project_title": p.title,
                            "hypothesis_statement": h.statement,
                            "date": u.timestamp, 
                            "content": u.content,
                            "evidence": u.evidence_status
                        })
    # Sort by date descending (newest first)
    author_updates.sort(key=lambda x: x["date"], reverse=True)
    return author_updates

def get_all_authors():
    """Iterates all hypotheses to find unique authors from updates."""
    authors = set()
    # Load all hypotheses directly
    data = _load_json(HYPOTHESES_FILE)
    
    for h_data in data.values():
        updates = h_data.get("updates", [])
        for u in updates:
            # u is a dict here since we loaded raw JSON
            auth_field = u.get("author")
            if auth_field:
                for auth in auth_field.replace(",", ";").split(";"):
                    clean_auth = auth.strip()
                    if clean_auth:
                        authors.add(clean_auth)
    return sorted(list(authors))

def get_updates_by_author(author_name: str):
    """Aggregates all updates by a specific author."""
    author_updates = []
    
    # Load all data
    hypotheses_data = _load_json(HYPOTHESES_FILE)
    projects_data = _load_json(PROJECTS_FILE)
    
    # Map project_id to title for easy lookup
    project_titles = {p_id: p_data["title"] for p_id, p_data in projects_data.items()}

    for h_data in hypotheses_data.values():
        updates = h_data.get("updates", [])
        for u in updates:
            # Check authors
            auth_field = u.get("author", "")
            current_authors = [a.strip() for a in auth_field.replace(",", ";").split(";")]
            
            if author_name in current_authors:
                p_id = h_data.get("project_id")
                p_title = project_titles.get(p_id, "Unknown Project")
                
                author_updates.append({
                    "project_title": p_title,
                    "hypothesis_statement": h_data.get("statement", ""),
                    "date": u.get("timestamp", ""), 
                    "content": u.get("content", ""),
                    "evidence": u.get("evidence_status", "")
                })
                
    # Sort by date descending
    author_updates.sort(key=lambda x: x["date"], reverse=True)
    return author_updates

def undo_last_action(project_id: str) -> bool:
    """
    Reverts the project to the previous snapshot state.
    Returns True if successful, False if no previous snapshot exists.
    """
    snapshots = get_snapshots(project_id)
    if len(snapshots) < 2:
        return False # No history to revert to
    
    # Current state is snapshots[0] (roughly, or internal state)
    # Target state is snapshots[1]
    target_ts = snapshots[1]
    bad_ts = snapshots[0]
    
    # Load target data
    target_data = load_snapshot_hypotheses(project_id, target_ts)
    
    if not target_data:
        return False
        
    global_data = _load_json(HYPOTHESES_FILE)
    
    # 1. Identify all hypotheses belonging to this project in Global Data
    #    and remove them/update them.
    ids_to_remove = []
    for h_id, h_data in global_data.items():
        if h_data.get("project_id") == project_id:
            ids_to_remove.append(h_id)
            
    for h_id in ids_to_remove:
        del global_data[h_id]
        
    # 2. Merge target_data into global_data
    global_data.update(target_data)
    
    _save_json(HYPOTHESES_FILE, global_data)
    
    # 3. Remove the 'bad' snapshot (the one we just undid from)
    snap_path = os.path.join(HISTORY_DIR, project_id, f"{bad_ts}.json")
    if os.path.exists(snap_path):
        os.remove(snap_path)
        
    return True

def get_hypotheses_by_project(project_id: str) -> List[Hypothesis]:
    data = _load_json(HYPOTHESES_FILE)
    results = []
    for h_data in data.values():
        if h_data.get("project_id") == project_id:
            # Reconstruct updates to satisfy dataclass
            raw_updates = h_data.get('updates', [])
            clean_updates = []
            for u in raw_updates:
                clean_updates.append(Update(**u))
            h_data['updates'] = clean_updates
            results.append(Hypothesis(**h_data))
    return results

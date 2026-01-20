import streamlit as st
import data_manager_sql as dm
from models import Project, Hypothesis
import time
# Replaced agraph with st_cytoscape
from st_cytoscape import cytoscape
import datetime
import os 

st.set_page_config(page_title="Research Manager", layout="wide")

st.markdown("""
<style>
    .hypothesis-card {
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-open { border-left: 5px solid #3498db; }
    .status-proven { border-left: 5px solid #2ecc71; }
    .status-disproven { border-left: 5px solid #e74c3c; }
    .status-tested { border-left: 5px solid #f1c40f; }
</style>
""", unsafe_allow_html=True)

def build_project_summary(project_id, snapshot_data=None):
    project = next((p for p in dm.get_projects() if p.id == project_id), None)
    if not project: return "Project not found."

    total_nodes = 0
    statuses = {"open": 0, "proven": 0, "disproven": 0, "tested": 0}
    max_depth = 0
    
    def traverse(h_id, depth):
        nonlocal total_nodes, max_depth
        h = dm.get_hypothesis(h_id, snapshot_data)
        if not h: return
        
        total_nodes += 1
        if h.status in statuses: statuses[h.status] += 1
        if depth > max_depth: max_depth = depth
        
        for child_id in h.children:
            traverse(child_id, depth + 1)
            
    traverse(project.north_star_hypothesis_id, 1)
    
    summary = f"""
    **Project Summary**
    - **Total Hypotheses**: {total_nodes}
    - **Max Depth**: {max_depth}
    - **Status Breakdown**:
        - ✅ Proven: {statuses['proven']}
        - ❌ Disproven: {statuses['disproven']}
        - ⚠️ Tested: {statuses['tested']}
        - 🟦 Open: {statuses['open']}
    """
    return summary

# --- CUSTOM TREE LAYOUT ALGORITHM ---
def calculate_tree_positions(root_id, snapshot_data=None):
    """
    Calculates deterministic (x, y) positions for a tree layout.
    """
    positions = {}
    
    # Store children map locally to avoid repeated DB calls
    node_map = {}
    
    def load_node(nid):
        if nid not in node_map:
            val = dm.get_hypothesis(nid, snapshot_data)
            if val:
                node_map[nid] = val
        return node_map.get(nid)

    # 1. Calculate Depths and Levels
    
    # Constants
    X_SPACING = 200
    Y_SPACING = 150
    
    def walk(node_id, depth):
        node = load_node(node_id)
        if not node: return 0
        
        # Traverse children first
        child_xs = []
        valid_children = [c for c in node.children if load_node(c)]
        
        for child_id in valid_children:
            cx = walk(child_id, depth + 1)
            child_xs.append(cx)
            
        current_x = 0
        if not valid_children:
             nonlocal leaf_counter
             current_x = leaf_counter * X_SPACING
             leaf_counter += 1
        else:
            # Parent is average of first and last child
             current_x = (child_xs[0] + child_xs[-1]) / 2.0
        
        positions[node_id] = {"x": current_x, "y": depth * Y_SPACING}
        return current_x
    
    leaf_counter = 0
    walk(root_id, 0)
    
    return positions

def build_cytoscape_elements(project_id: str, north_star_id: str, snapshot_data=None, default_positions=None, force_positions=False):
    # Calculate positions via backend engine if strict forced
    if force_positions:
         positions = calculate_tree_positions(north_star_id, snapshot_data)
    else:
         positions = default_positions or {}
         
    elements = []
    
    def traverse(h_id):
        h = dm.get_hypothesis(h_id, snapshot_data)
        if not h: return
        
        # Short label used by default style
        clean_stmt = h.statement.replace("\n", " ")
        short = clean_stmt[:20] + "..." if len(clean_stmt) > 20 else clean_stmt
        
        node_data = {
            "data": {
                "id": h.id,
                "label": short, 
                "full_label": h.statement,
                "status": h.status
            }
        }
        
        # Inject Position
        # 1. Force override (Strict Tree)
        if force_positions and h.id in positions:
             node_data["position"] = positions[h.id]
        # 2. Manual Custom: Use DB position if set
        elif h.position and "x" in h.position:
             node_data["position"] = h.position
        # 3. Fallback to default if available
        elif h.id in positions: 
             node_data["position"] = positions[h.id]
        
        # If no position is set, Cytoscape preset layout might place it at 0,0, so we ensured defaults
            
        elements.append(node_data)
        
        for child_id in h.children:
            edge_id = f"e_{h.id}_{child_id}"
            elements.append({
                "data": {
                    "id": edge_id,
                    "source": h.id,
                    "target": child_id,
                }
            })
            traverse(child_id)

    traverse(north_star_id)
    # Sort elements by ID
    elements.sort(key=lambda x: x["data"]["id"])
    return elements

def main():
    st.sidebar.title("Research Manager")
    
    if "nav_request" in st.session_state and st.session_state["nav_request"]:
        st.session_state["current_page"] = st.session_state["nav_request"]
        st.session_state["nav_request"] = None

    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Dashboard"
        
    page = st.sidebar.radio("Navigate", ["Dashboard", "Project View", "People View"], key="current_page")
    
    if page == "Dashboard":
        st.title("Projects Dashboard")
        
        with st.form("new_project"):
            st.subheader("Start New Project")
            title = st.text_input("Project Title")
            north_star = st.text_input("North Star Hypothesis")
            if st.form_submit_button("Create Project"):
                if title and north_star:
                    dm.create_project(title, north_star)
                    st.success(f"Project '{title}' created!")
                    time.sleep(1)
                    st.rerun()
        
        st.divider()
        st.subheader("Active Projects")
        projects = dm.get_projects()
        for p in projects:
            with st.container():
                col1, col2 = st.columns([0.8, 0.2])
                col1.markdown(f"### {p.title}")
                col1.caption(f"Status: {p.status}")
                if col2.button(f"Open", key=p.id):
                    st.session_state["active_project"] = p.id
                    st.session_state["nav_request"] = "Project View"
                    st.rerun() 

    elif page == "Project View":
        if "active_project" not in st.session_state:
            st.warning("Please select a project from Dashboard")
            return

        projects = dm.get_projects()
        project = next((p for p in projects if p.id == st.session_state["active_project"]), None)
        if not project:
            st.error("Project not found")
            return

        st.title(f"Project: {project.title}")
        
        st.sidebar.divider()
        st.sidebar.header("Project Actions")
        
        # Report Generation
        report_md = dm.generate_project_report(project.id)
        st.sidebar.download_button(
             label="📄 Download Report (MD)",
             data=report_md,
             file_name=f"report_{project.title}_{int(time.time())}.md",
             mime="text/markdown"
        )

        st.sidebar.header("History & Versioning")
        snapshots = dm.get_snapshots(project.id)
        
        selected_snapshot_ts = None
        if snapshots:
            options = ["Current"] + [datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') for ts in snapshots]
            selection = st.sidebar.selectbox("View Version", options)
            
            if selection != "Current":
                idx = options.index(selection) - 1
                selected_snapshot_ts = snapshots[idx]
                st.warning(f"Viewing historical version: {selection}. Read-only Mode.")

        snapshot_data = None
        if selected_snapshot_ts:
            snapshot_data = dm.load_snapshot_hypotheses(project.id, selected_snapshot_ts)

        # --- LAYOUT CONTROL (REMOVED DROPDOWN) ---
        
        col_graph, col_controls = st.columns([0.7, 0.3])
         
        # Enforce 'breadthfirst'
        new_db_mode = "breadthfirst"
        
        # Persist if changed
        if getattr(project, "layout_mode", "") != new_db_mode:
             project.layout_mode = new_db_mode
             dm.save_project(project)
        
        if "graph_version" not in st.session_state:
            st.session_state["graph_version"] = 0

        # 2. Configure Layout (Always Breadthfirst)
        layout_config = {
             "name": "breadthfirst",
             "directed": True,
             "spacingFactor": 1.5,
             "grid": True,
             "roots": f"[id = '{project.north_star_hypothesis_id}']",
             "animate": True,
             "animationDuration": 500
        }
        
        positions = {}
        force_positions = False
        
        with col_graph:
            elements = build_cytoscape_elements(
                project.id, 
                project.north_star_hypothesis_id, 
                snapshot_data, 
                default_positions=positions, # Fallback
                force_positions=force_positions
            )
            
            stylesheet = [
                {
                    "selector": "node",
                    "style": {
                        "label": "data(label)",
                        "width": 60,
                        "height": 60,
                        "font-size": 10,
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": 55,
                        "background-color": "#ecf0f1",
                        "color": "#2c3e50",
                        "text-background-opacity": 0,
                    }
                },
                {
                    "selector": "node:active",
                    "style": {
                        "label": "data(full_label)",
                        "text-max-width": 200,
                        "min-zoomed-font-size": 0,
                        "z-index": 9999,
                        "text-background-opacity": 1,
                        "text-background-color": "white",
                        "text-background-shape": "round-rectangle",
                        "text-background-padding": "5px",
                        "text-border-width": 1,
                        "text-border-color": "#ccc"
                    }
                },
                {
                    "selector": "node:selected",
                    "style": {
                         "border-width": 4,
                         "border-color": "#34495e"
                    }
                },
                {"selector": "node[status='proven']", "style": {"background-color": "#2ecc71"}},
                {"selector": "node[status='disproven']", "style": {"background-color": "#e74c3c"}},
                {"selector": "node[status='tested']", "style": {"background-color": "#f1c40f"}},
                {"selector": "node[status='open']", "style": {"background-color": "#3498db"}},
                {
                    "selector": "edge",
                    "style": {
                        "width": 3,
                        "curve-style": "bezier",
                        "target-arrow-shape": "triangle",
                        "line-color": "#95a5a6",
                        "target-arrow-color": "#95a5a6"
                    }
                },
                {"selector": "edge:selected", "style": {"line-color": "#e74c3c", "target-arrow-color": "#e74c3c", "width": 6}}
            ]

            # Render
            selected_element = cytoscape(
                elements,
                stylesheet,
                layout_config,
                # Force re-render if graph_version changes (on Save)
                key=f"cyto_{project.id}_{new_db_mode}_{st.session_state['graph_version']}", 
                height="600px",
                user_zooming_enabled=True,
                user_panning_enabled=True,
                min_zoom=0.5, 
                max_zoom=2.5,
                selection_type="single", 
            )

        with col_controls:
            
            st.subheader("Settings")
            # --- UNDO OPERATIONS ---
            snap_list = dm.get_snapshots(project.id)
            if len(snap_list) >= 2 and not selected_snapshot_ts:
                if st.button("↩️ Undo Last Change", help="Revert the last topology change (Delete, Reverse, etc.)"):
                     if dm.undo_last_action(project.id):
                         st.success("Undone!")
                         time.sleep(0.5)
                         st.session_state["graph_version"] += 1
                         st.rerun()
                     else:
                         st.error("Could not undo.")

            # --- SELECTION & MANUAL CONTROLS ---
            clicked_node_id = None
            clicked_node_position = None
            clicked_edge_id = None 

            if selected_element:
                s_nodes = selected_element.get("nodes", [])
                s_edges = selected_element.get("edges", [])
                
                if s_nodes:
                    first_node = s_nodes[0]
                    if isinstance(first_node, dict):
                        clicked_node_id = first_node.get("data", {}).get("id") or first_node.get("id")
                        clicked_node_position = first_node.get("position")
                    elif isinstance(first_node, str):
                        clicked_node_id = first_node

                elif s_edges:
                    first_edge = s_edges[0]
                    if isinstance(first_edge, str):
                        clicked_edge_id = first_edge
                    elif isinstance(first_edge, dict):
                         clicked_edge_id = first_edge.get("data", {}).get("id") or first_edge.get("id")

            if clicked_node_id and not selected_snapshot_ts:
                h_clicked = dm.get_hypothesis(clicked_node_id, snapshot_data)
                
                if h_clicked:
                    
                    st.divider()
                    st.markdown(f"**Selected: {h_clicked.statement[:30]}...**")
                    
                    # Position controls removed (Cleanup)

                    st.caption(f"Status: {h_clicked.status}")

                    with st.expander("Scientific Evidence", expanded=True):
                        # Scrollable container for reading evidence
                        with st.container(height=200):
                            if h_clicked.updates:
                                for u in h_clicked.updates:
                                    icon = "⬜"
                                    if u.evidence_status == "supporting": icon = "✅"
                                    elif u.evidence_status == "refuting": icon = "❌"
                                    st.markdown(f"{icon} **{u.author}**: {u.content}")
                            else:
                                st.caption("No evidence logged.")
                            
                        st.divider()
                        action = st.radio("Log Data", ["Update", "Set Status"], key=f"sci_act_{h_clicked.id}")
                        if action == "Update":
                             with st.form(f"up_{h_clicked.id}"):
                                existing_authors = dm.get_all_authors()
                                author_options = existing_authors + ["➕ New Author..."]
                                sel_auth = st.selectbox("Author", author_options)
                                
                                if sel_auth == "➕ New Author...":
                                    final_auth = st.text_input("Enter Author Name")
                                else:
                                    final_auth = sel_auth
                                    
                                cont = st.text_area("Content")
                                ev = st.selectbox("Type", ["neutral", "supporting", "refuting"])
                                if st.form_submit_button("Log"):
                                    if final_auth and cont:
                                        dm.add_update(h_clicked.id, final_auth, cont, {}, ev)
                                        st.rerun()

                        elif action == "Set Status":
                            ns = st.selectbox("Status", ["open", "tested", "proven", "disproven"])
                            if st.button("Update"):
                                h_clicked.status = ns
                                dm.save_hypothesis(h_clicked)
                                st.rerun()

                    st.divider()
                    st.markdown("#### Node Operations")
                    if st.button("🗑️ Delete Node & Children", type="primary"):
                         dm.delete_hypothesis(h_clicked.id)
                         st.rerun()
                         
                    with st.form(f"quick_add_{clicked_node_id}"):
                        new_stmt = st.text_input("Add Child", label_visibility="collapsed", placeholder="New sub-hypothesis...")
                        if st.form_submit_button("Add"):
                            dm.add_subhypothesis(clicked_node_id, new_stmt)
                            st.rerun()

            elif clicked_edge_id and not selected_snapshot_ts:
                parts = clicked_edge_id.split("_")
                if len(parts) >= 3:
                    source_id = parts[1]
                    target_id = parts[2]
                    
                    st.info(f"**Selected Edge**")
                    col_rev, col_del = st.columns(2)
                    with col_rev:
                        if st.button("🔄 Reverse Direction"):
                            dm.reverse_relationship(target_id)
                            st.rerun()
                    with col_del:
                        if st.button("✂️ Delete Edge"):
                             st.session_state["confirm_delete_edge"] = clicked_edge_id
                             st.rerun()
                    
                    if "confirm_delete_edge" in st.session_state and st.session_state["confirm_delete_edge"] == clicked_edge_id:
                         # ... delete branch logic ...
                        if st.button("Confirm Delete Branch", type="primary"):
                            dm.delete_hypothesis(target_id)
                            del st.session_state["confirm_delete_edge"]
                            st.rerun()
            elif not clicked_node_id and not clicked_edge_id:
                  st.info("Select a node or edge to view details.")

        st.divider()
        st.subheader("Project Overview")
        st.markdown(build_project_summary(project.id, snapshot_data))

    elif page == "People View":
        # ... People View Code ...
        st.title("People & Contributions")
        col_list, col_details = st.columns([0.25, 0.75])
        authors = dm.get_all_authors()
        with col_list:
            if authors:
                selected_author = st.radio("Select Person", authors)
            else:
                 st.info("No authors found yet.")
                 selected_author = None
        with col_details:
             if selected_author:
                  updates = dm.get_updates_by_author(selected_author)
                  st.header(f"👤 {selected_author}")
                  # ... summary code ...
                  st.markdown("### 🤖 AI Activity Summary")
                  st.info(f"Analysis for {selected_author}: ...")
                  
                  st.divider()
                  for update in updates:
                      with st.container():
                            st.markdown(f"**{update['date'][:10]}** | *{update['project_title']}*")
                            st.markdown(f"> **Hypothesis:** {update['hypothesis_statement']}")
                            icon = "⬜"
                            if update['evidence'] == "supporting": icon = "✅"
                            elif update['evidence'] == "refuting": icon = "❌"
                            st.markdown(f"{icon} {update['content']}")
                            st.divider()

if __name__ == "__main__":
    main()

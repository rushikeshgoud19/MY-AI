import os
import sqlite3
import json
import logging

from server.config import log_info

def get_graph_data():
    """Returns the knowledge graph nodes and links as a dictionary."""
    nodes = []
    links = []
    
    # 1. Root Node
    nodes.append({"id": "Mizune Core", "name": "Mizune's Brain", "group": 0, "val": 20})
    
    # 2. Extract Skills
    skills_dir = ".data/skills/active"
    if os.path.exists(skills_dir):
        for filename in os.listdir(skills_dir):
            if filename.endswith(".py"):
                skill_name = filename[:-3]
                node_id = f"Skill: {skill_name}"
                nodes.append({"id": node_id, "name": skill_name, "group": 1, "val": 10})
                links.append({"source": "Mizune Core", "target": node_id})
                
    # 3. Extract Sessions (SQLite)
    data_dir = ".data"
    telemetry_dir = "data_collector"
    db_path = os.path.join(telemetry_dir, "mizune_memory.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT role, content FROM conversation_log ORDER BY timestamp DESC LIMIT 30")
            rows = c.fetchall()
            for i, row in enumerate(rows):
                role, content = row
                node_id = f"Session_{i}"
                nodes.append({"id": node_id, "name": f"{role.upper()}: {content[:30]}...", "group": 2, "val": 5})
                
                # Link to core
                if i % 3 == 0:
                    links.append({"source": "Mizune Core", "target": node_id})
                    
                # Link sequentially for timeline
                if i > 0:
                    links.append({"source": f"Session_{i-1}", "target": node_id})
            conn.close()
        except Exception as e:
            log_info(f"[KNOWLEDGE GRAPH] Error reading SQLite: {e}")
            
    # 4. Extract ChromaDB Semantic Memories
    try:
        from server.memory import memory
        if memory and memory.collection:
            # Get all documents but slice to limit the graph size
            results = memory.collection.get()
            docs = results.get('documents', [])
            # Limit to 50 nodes to avoid massive UI lag on the frontend
            docs = docs[-50:] if len(docs) > 50 else docs
            for i, doc in enumerate(docs):
                node_id = f"Semantic_{i}"
                nodes.append({"id": node_id, "name": doc[:40] + "...", "group": 3, "val": 8})
                links.append({"source": "Mizune Core", "target": node_id})
    except Exception as e:
        log_info(f"[KNOWLEDGE GRAPH] Error reading ChromaDB: {e}")
            
    return {"nodes": nodes, "links": links}

def generate_graph_html(output_path="memory_graph.html"):
    """
    Scans Mizune's memory systems (Skills, SQLite History, ChromaDB) 
    and generates an interactive 3D WebGL Knowledge Graph HTML file.
    """
    log_info("[KNOWLEDGE GRAPH] Generating 3D Memory Graph...")
    graph_data = get_graph_data()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Mizune Knowledge Graph</title>
      <style> 
        body {{ margin: 0; background-color: #0b0f19; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; overflow: hidden; }} 
        #legend {{ position: absolute; top: 20px; left: 20px; z-index: 100; background: rgba(0,0,0,0.7); padding: 15px; border-radius: 10px; border: 1px solid #333; }}
        h2 {{ margin-top: 0; background: -webkit-linear-gradient(#00ffff, #ff00ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
      </style>
      <script src="https://unpkg.com/3d-force-graph"></script>
    </head>
    <body>
      <div id="legend">
          <h2>Neural Memory Graph</h2>
          <div style="color: #4CAF50;">● Core Network</div>
          <div style="color: #ff00ff;">● Acquired Skills</div>
          <div style="color: #00ffff;">● Session Timeline</div>
          <div style="color: #ffff00;">● Semantic Memories</div>
      </div>
      <div id="3d-graph"></div>
      
      <script>
        const gData = {json.dumps(graph_data)};
        
        // Custom color mapping based on groups
        const colorMap = {{
            0: '#4CAF50', // Core
            1: '#ff00ff', // Skills
            2: '#00ffff', // Sessions
            3: '#ffff00'  // Semantic
        }};
        
        const Graph = ForceGraph3D()
          (document.getElementById('3d-graph'))
            .graphData(gData)
            .nodeLabel('name')
            .nodeColor(node => colorMap[node.group] || '#ffffff')
            .nodeRelSize(5)
            .linkDirectionalParticles(2)
            .linkDirectionalParticleSpeed(0.005)
            .linkDirectionalParticleWidth(1.5)
            .linkColor(() => 'rgba(255,255,255,0.2)');
            
        // Orbit camera automatically
        let angle = 0;
        setInterval(() => {{
            angle += Math.PI / 1000;
            Graph.cameraPosition({{
                x: 300 * Math.sin(angle),
                z: 300 * Math.cos(angle)
            }});
        }}, 20);
      </script>
    </body>
    </html>
    """
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    log_info(f"[KNOWLEDGE GRAPH] Successfully saved 3D Graph to {output_path}")
    return output_path

if __name__ == "__main__":
    generate_graph_html()

import os
import sqlite3
import json
import logging

from server.config import log_info

def get_graph_data():
    """Build Mizune's knowledge graph from REAL memory relationships.

    Edges come from actual data — topics.related_topics, entity co-occurrence in
    emotional_memory events, connection_strength interaction weights, and
    which topics each memory/document actually mentions — not decorative links.

    Groups: 0=core, 1=skills, 2=memories, 3=semantic docs, 4=topics, 5=people.
    """
    nodes = []
    links = []
    node_ids = set()

    def add_node(nid, name, group, val):
        if nid in node_ids:
            return
        node_ids.add(nid)
        nodes.append({"id": nid, "name": name, "group": group, "val": val})

    def add_link(a, b, strength=1.0):
        if a in node_ids and b in node_ids and a != b:
            links.append({"source": a, "target": b, "value": round(float(strength), 2)})

    def link_by_mentions(nid, text, topic_names, fallback_strength=0.5):
        """Link a node to every topic its text actually mentions."""
        lowered = (text or "").lower()
        linked = False
        for tname, tnode in topic_names.items():
            if len(tname) >= 3 and tname in lowered:
                add_link(nid, tnode)
                linked = True
        if not linked:
            add_link("Mizune Core", nid, strength=fallback_strength)

    add_node("Mizune Core", "Mizune's Brain", 0, 20)

    # ── Memory Tree: topics, co-occurrence, connection strength, summaries ──
    topic_names = {}  # lowercase entity name -> node id
    try:
        from server.memory_tree import memory_tree_db
        db = getattr(memory_tree_db, "db", None)
        if db:
            cur = db.cursor()

            # 1. Topics — the entities Mizune actually knows about, sized by hotness
            topic_rows = cur.execute(
                "SELECT entity_name, entity_type, hotness, related_topics FROM topics "
                "ORDER BY hotness DESC LIMIT 60"
            ).fetchall()
            for name, ttype, hotness, _related in topic_rows:
                if not name:
                    continue
                group = 5 if ttype == "person" else 4
                nid = f"Topic: {name}"
                add_node(nid, str(name), group, 6 + min(float(hotness or 0), 10))
                topic_names[str(name).lower()] = nid

            # 2. Real topic-to-topic edges from related_topics
            for name, _ttype, _hot, related in topic_rows:
                if not (name and related):
                    continue
                try:
                    rel = json.loads(related)
                except Exception:
                    continue
                src = f"Topic: {name}"
                for r in (rel if isinstance(rel, list) else []):
                    dst = topic_names.get(str(r).lower())
                    if dst:
                        add_link(src, dst)

            # 3. Co-occurrence edges: entities that appeared in the same events
            import collections
            pair_counts = collections.Counter()
            for (ents,) in cur.execute(
                "SELECT entities FROM emotional_memory WHERE entities IS NOT NULL "
                "ORDER BY timestamp DESC LIMIT 300"
            ).fetchall():
                try:
                    elist = {str(e).lower() for e in json.loads(ents) if e}
                except Exception:
                    continue
                known = sorted(e for e in elist if e in topic_names)
                for i in range(len(known)):
                    for j in range(i + 1, len(known)):
                        pair_counts[(known[i], known[j])] += 1
            for (a, b), cnt in pair_counts.most_common(80):
                add_link(topic_names[a], topic_names[b], strength=min(cnt, 5))

            # 4. Bond strength: entities anchored to the core by real interaction weight
            for entity, strength, _count in cur.execute(
                "SELECT entity, strength, interaction_count FROM connection_strength "
                "ORDER BY strength DESC LIMIT 30"
            ).fetchall():
                if not entity:
                    continue
                nid = topic_names.get(str(entity).lower())
                if not nid:
                    nid = f"Topic: {entity}"
                    add_node(nid, str(entity), 4, 6)
                    topic_names[str(entity).lower()] = nid
                add_link("Mizune Core", nid, strength=max(float(strength or 0.5), 0.5))

            # 5. Recent compressed memories, linked to the topics they mention
            for sid, content in cur.execute(
                "SELECT id, content FROM episodic WHERE source = 'summary' "
                "ORDER BY timestamp DESC LIMIT 30"
            ).fetchall():
                nid = f"Memory_{sid}"
                add_node(nid, (content or "")[:48] + "...", 2, 5)
                link_by_mentions(nid, content, topic_names)
    except Exception as e:
        log_info(f"[KNOWLEDGE GRAPH] Error reading memory tree: {e}")

    # ── Contacts: real people, weighted by real message volume ──
    if os.path.exists("cortex.db"):
        try:
            conn = sqlite3.connect("cortex.db")
            c = conn.cursor()
            for name, tier, rel_score, msg_count in c.execute(
                "SELECT name, tier, relationship_score, message_count FROM contacts "
                "WHERE name IS NOT NULL ORDER BY message_count DESC LIMIT 25"
            ).fetchall():
                nid = topic_names.get(str(name).lower()) or f"Person: {name}"
                if nid not in node_ids:
                    add_node(nid, str(name), 5, 6 + min((msg_count or 0) / 50.0, 8))
                    topic_names[str(name).lower()] = nid
                add_link("Mizune Core", nid, strength=max(float(rel_score or 1), 1))
            conn.close()
        except Exception as e:
            log_info(f"[KNOWLEDGE GRAPH] Error reading contacts: {e}")

    # ── Skills: capabilities Mizune owns ──
    skills_dir = ".data/skills/active"
    if os.path.exists(skills_dir):
        for filename in os.listdir(skills_dir):
            if filename.endswith(".py"):
                skill_name = filename[:-3]
                nid = f"Skill: {skill_name}"
                add_node(nid, skill_name, 1, 10)
                add_link("Mizune Core", nid)

    # ── ChromaDB semantic memories, linked to the topics they mention ──
    try:
        import chromadb
        chroma_dir = os.path.join(".data", "chroma_db")
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_or_create_collection(name="mizune_longterm")
        results = collection.get()
        docs = results.get('documents', [])
        # Limit to 50 nodes to avoid massive UI lag on the frontend
        docs = docs[-50:] if len(docs) > 50 else docs
        for i, doc in enumerate(docs):
            nid = f"Semantic_{i}"
            add_node(nid, doc[:40] + "...", 3, 8)
            link_by_mentions(nid, doc, topic_names)
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
          <div style="color: #00ffff;">● Compressed Memories</div>
          <div style="color: #ffff00;">● Semantic Memories</div>
          <div style="color: #ff9800;">● Topics</div>
          <div style="color: #2196f3;">● People</div>
      </div>
      <div id="3d-graph"></div>
      
      <script>
        const gData = {json.dumps(graph_data)};
        
        // Custom color mapping based on groups
        const colorMap = {{
            0: '#4CAF50', // Core
            1: '#ff00ff', // Skills
            2: '#00ffff', // Compressed memories
            3: '#ffff00', // Semantic
            4: '#ff9800', // Topics
            5: '#2196f3'  // People
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

import React, { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface Node {
  id: string;
  name: string;
  group: number;
  val: number;
}

interface Link {
  source: string;
  target: string;
}

interface GraphData {
  nodes: Node[];
  links: Link[];
}

export const MemoryGraph: React.FC = () => {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    // Update dimensions on resize
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    
    // Connect to websocket to fetch data
    const ws = new WebSocket('ws://localhost:8001/ws');
    
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'get_knowledge_graph' }));
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'knowledge_graph_data') {
          setGraphData(data.payload);
          setLoading(false);
        }
      } catch (e) {
        console.error("Error parsing graph data:", e);
      }
    };
    
    return () => {
      window.removeEventListener('resize', updateDimensions);
      ws.close();
    };
  }, []);

  const colorMap: Record<number, string> = {
    0: '#4CAF50', // Core
    1: '#ff00ff', // Skills
    2: '#00ffff', // Sessions
    3: '#ffff00'  // Semantic
  };

  return (
    <div className="panel-container memory-graph-panel" ref={containerRef} style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '24px', paddingBottom: '0' }}>
        <h2>Neural Memory Graph</h2>
        <div className="graph-legend" style={{ display: 'flex', gap: '16px', fontSize: '12px', marginBottom: '16px' }}>
          <span style={{ color: colorMap[0] }}>● Core Network</span>
          <span style={{ color: colorMap[1] }}>● Acquired Skills</span>
          <span style={{ color: colorMap[2] }}>● Session Timeline</span>
          <span style={{ color: colorMap[3] }}>● Semantic Memories</span>
        </div>
      </div>
      
      <div style={{ flex: 1, position: 'relative' }}>
        {loading ? (
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
            <div className="pulse" style={{ width: '40px', height: '40px', background: '#a855f7' }} />
          </div>
        ) : (
          <ForceGraph2D
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            nodeLabel="name"
            nodeColor={(node: any) => colorMap[node.group] || '#ffffff'}
            nodeRelSize={5}
            linkColor={() => 'rgba(255,255,255,0.2)'}
            linkWidth={1.5}
            linkDirectionalParticles={2}
            linkDirectionalParticleSpeed={0.005}
            backgroundColor="transparent"
          />
        )}
      </div>
    </div>
  );
};

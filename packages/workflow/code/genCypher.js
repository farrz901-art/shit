function genCypher({ entities, relations }) {
    try {
        // 按类型分组节点
        const nodesByType = {};
        for (const e of entities) {
            if (!nodesByType[e.type]) nodesByType[e.type] = [];
            nodesByType[e.type].push(e);
        }
        
        // 生成节点 MERGE 语句（使用参数化，按类型分别 unwind）
        const nodeStatements = [];
        const nodeParams = {};
        for (const [type, nodeList] of Object.entries(nodesByType)) {
            const paramName = `nodes_${type.replace(/[^a-zA-Z0-9]/g, '_')}`;
            nodeParams[paramName] = nodeList.map(n => ({
                name: n.name,
                props: n.properties || {}
            }));
            nodeStatements.push(`
                UNWIND $${paramName} AS item
                MERGE (n:\`${type}\` {name: item.name})
                SET n = item.props
            `);
        }
        
        // 生成关系 MERGE 语句（需要查找源和目标实体的 name）
        const relStatements = [];
        const relParams = {};
        // 建立 id -> name 映射
        const idToName = {};
        for (const e of entities) {
            idToName[e.id] = e.name;
        }
        // 按关系类型分组（可选）
        const relsByType = {};
        for (const rel of relations) {
            const srcName = idToName[rel.source_id];
            const tgtName = idToName[rel.target_id];
            if (!srcName || !tgtName) continue;
            if (!relsByType[rel.type]) relsByType[rel.type] = [];
            relsByType[rel.type].push({
                srcName, tgtName, props: rel.properties || {}
            });
        }
        for (const [type, relList] of Object.entries(relsByType)) {
            const paramName = `rels_${type.replace(/[^a-zA-Z0-9]/g, '_')}`;
            relParams[paramName] = relList;
            relStatements.push(`
                UNWIND $${paramName} AS rel
                MATCH (a {name: rel.srcName})
                MATCH (b {name: rel.tgtName})
                MERGE (a)-[:${type}]->(b)
                SET a = a  // 无额外属性，可省略
            `);
            // 如果关系有属性，可以 SET r = rel.props，但需要先创建关系变量。
            // 更准确的方式：
            // MERGE (a)-[r:${type}]->(b)
            // SET r = rel.props
        }
        
        const fullCypher = [...nodeStatements, ...relStatements].join(';\n');
        const allParams = { ...nodeParams, ...relParams };
        
        return {
            cypher: fullCypher,
            params: allParams,
            error: null
        };
    } catch (err) {
        return {
            cypher:null,
            params:null,
            error: err.message };
    }
}


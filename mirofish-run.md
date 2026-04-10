# MiroFish — Claude Code Agent Team Runner

Esegui una simulazione predittiva MiroFish interamente con Claude Code agent team.
Nessuna API key necessaria — tutto il lavoro LLM viene fatto dagli agenti Claude Code.

## Input

L'utente fornisce:
1. Un file seed (PDF, MD, o TXT) o testo diretto
2. Una domanda/scenario predittivo

## Esecuzione

Esegui i 5 step in sequenza. Ogni step produce file JSON/MD nella directory di lavoro `~/projects/mirofish/runs/<run-id>/`.

---

### Step 1 — Ontology Extraction

Lancia 1 agente Haiku:

```
Agent(subagent_type="general-purpose", model="haiku", prompt="""
Analizza questo documento e estrai un'ontologia per la simulazione.

DOCUMENTO:
{contenuto del file seed}

SCENARIO:
{domanda predittiva dell'utente}

Restituisci JSON con esattamente 10 entity types (8 specifici al dominio + Person + Organization)
e 6-10 edge types. Formato:
{
  "entity_types": [{"name": "PascalCase", "description": "..."}],
  "edge_types": [{"name": "UPPER_SNAKE_CASE", "source": "...", "target": "...", "description": "..."}]
}
""")
```

Salva output in `ontology.json`.

---

### Step 2 — Knowledge Graph + Entity Extraction

Lancia 3 agenti Haiku in parallelo, ognuno analizza 1/3 del documento:

```
Agent(subagent_type="general-purpose", model="haiku", prompt="""
Dato questo testo e questa ontologia, estrai TUTTE le entita' e relazioni.

ONTOLOGIA: {ontology.json}
TESTO (chunk {N}/3): {chunk}

Restituisci JSON:
{
  "entities": [{"name": "...", "type": "EntityType", "description": "...", "attributes": {}}],
  "relations": [{"source": "name", "relation": "EDGE_TYPE", "target": "name", "fact": "..."}]
}
""")
```

Merge i 3 risultati, dedup entita' per nome, salva `graph.json`.

---

### Step 3 — Agent Profile Generation

Lancia 1 agente Sonnet per generare i profili degli agenti simulati:

```
Agent(subagent_type="general-purpose", model="sonnet", prompt="""
Genera profili social media per questi agenti basandoti sul knowledge graph.

ENTITA': {lista entita' dal graph.json}
RELAZIONI: {lista relazioni}
SCENARIO: {scenario utente}

Per ogni entita' di tipo Person/Organization (o tipo rilevante), genera un profilo:
{
  "agents": [
    {
      "id": "agent_1",
      "name": "...",
      "username": "@...",
      "bio": "max 200 char",
      "persona": "2000 char personality description",
      "age": N, "gender": "...", "mbti": "XXXX",
      "profession": "...",
      "stance": "their position on the scenario",
      "topics": ["topic1", "topic2"],
      "activity_level": 0.0-1.0
    }
  ]
}

Genera 8-15 agenti diversificati con stance contrastanti.
""")
```

Salva `profiles.json`.

---

### Step 4 — Social Simulation (3-5 round)

Per ogni round, lancia N agenti Haiku in parallelo (1 per agente simulato):

```
Per round = 1..5:
  Per ogni agent in profiles:
    Agent(model="haiku", prompt="""
    Sei {agent.name}. {agent.persona}
    Stance: {agent.stance}. Topics: {agent.topics}

    FEED CORRENTE (post degli altri agenti questo round):
    {posts dal round precedente}

    Scegli UN'AZIONE e rispondi JSON:
    {"action": "CREATE_POST|COMMENT|LIKE|REPOST|DO_NOTHING",
     "content": "testo del post/commento se applicabile",
     "target_post": "id del post se commenti/like/repost",
     "reasoning": "perche' hai scelto questa azione"}
    """)

  Raccogli tutte le azioni, aggiorna il feed, salva `round_{N}.json`
```

Salva `simulation_timeline.json` con tutti i round.

---

### Step 5 — Report Generation

Lancia 1 agente Opus per analizzare tutto e generare il report:

```
Agent(subagent_type="general-purpose", model="opus", prompt="""
Sei un analista esperto. Genera un report predittivo basato su questa simulazione.

SCENARIO: {domanda utente}
KNOWLEDGE GRAPH: {graph.json - entita' e relazioni chiave}
PROFILI AGENTI: {profiles.json - chi sono gli agenti}
TIMELINE SIMULAZIONE: {simulation_timeline.json - tutte le interazioni}

Analizza:
1. Pattern emergenti nelle interazioni
2. Consenso vs dissenso tra gli agenti
3. Topic piu' discussi e sentiment
4. Previsione basata sul comportamento collettivo

Genera un report in Markdown con:
- Executive Summary
- Analisi delle Dinamiche Sociali
- Pattern Emergenti
- Previsione e Scenari
- Evidenze dalla Simulazione (cita post specifici)

Min 1500 parole. Cita evidenze specifiche dai post degli agenti.
""")
```

Salva `report.md`.

---

## Output

Mostra all'utente:
1. Sommario: N entita', N relazioni, N agenti, N round, N post totali
2. Il report completo
3. Path dei file generati

## Costi stimati (Claude Max)

| Step | Modello | Agenti | Token stimati |
|------|---------|--------|---------------|
| 1. Ontology | Haiku | 1 | ~2K |
| 2. Graph | Haiku | 3 | ~6K |
| 3. Profiles | Sonnet | 1 | ~4K |
| 4. Simulation | Haiku | 10-15 x 5 round | ~30K |
| 5. Report | Opus | 1 | ~8K |
| **Totale** | | ~55-80 | **~50K token** |

Con Claude Max: costo effettivamente zero (incluso nell'abbonamento).

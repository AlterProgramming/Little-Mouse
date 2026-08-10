#!/usr/bin/env python3
"""Render a self-contained HTML viewer for a Little Mouse temporal trace ledger."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def render(ledger: dict[str, Any], title: str = "Little Mouse Trace Viewer") -> str:
    payload = json.dumps(ledger, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(title)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title>
<style>
:root {{ color-scheme: light dark; --bg:#0f1115; --panel:#171a21; --ink:#eef2f7; --muted:#9aa4b2; --line:#2b3240; --accent:#8ab4f8; --good:#8bd5ca; }}
@media (prefers-color-scheme: light) {{ :root {{ --bg:#f5f7fb; --panel:#ffffff; --ink:#172033; --muted:#637083; --line:#dce2ec; --accent:#2457c5; --good:#157a6e; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:14px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--ink); }}
header {{ padding:24px max(20px,4vw) 14px; position:sticky; top:0; background:color-mix(in srgb,var(--bg) 92%,transparent); backdrop-filter:blur(12px); z-index:4; border-bottom:1px solid var(--line); }}
h1 {{ margin:0 0 6px; font-size:22px; }} header p {{ margin:0; color:var(--muted); max-width:900px; }}
main {{ padding:20px max(20px,4vw) 50px; display:grid; gap:18px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }}
.card,.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; }}
.card {{ padding:14px; }} .card b {{ display:block; font-size:24px; margin-top:3px; }} .card span {{ color:var(--muted); }}
.panel {{ padding:16px; }} .panel h2 {{ font-size:16px; margin:0 0 12px; }}
.controls {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }}
button {{ border:1px solid var(--line); background:transparent; color:var(--ink); padding:7px 10px; border-radius:999px; cursor:pointer; }} button.active {{ border-color:var(--accent); color:var(--accent); }}
.timeline {{ display:grid; gap:8px; }} .event {{ display:grid; grid-template-columns:minmax(145px,190px) 16px 1fr; gap:10px; align-items:start; }}
.when {{ color:var(--muted); font-variant-numeric:tabular-nums; font-size:12px; padding-top:2px; }}
.dot {{ width:10px; height:10px; border-radius:50%; background:var(--accent); margin-top:5px; box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent); }}
.event-body {{ border-left:1px solid var(--line); padding:0 0 12px 12px; min-height:34px; }} .action {{ font-weight:650; }} .meta {{ color:var(--muted); font-size:12px; margin-top:2px; }}
.alias-grid {{ display:grid; gap:10px; }} .alias-person {{ padding:10px 0; border-top:1px solid var(--line); }} .alias-person:first-child {{ border-top:0; }}
.alias-chip {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:3px 8px; margin:3px 4px 0 0; }}
small.note {{ color:var(--muted); display:block; margin-top:8px; }} .trace-map {{ width:100%; min-height:260px; overflow:auto; }}
svg {{ width:100%; height:300px; }} .edge {{ stroke:var(--line); stroke-width:1.2; }} .node {{ fill:var(--panel); stroke:var(--accent); stroke-width:1.5; }} .actor {{ stroke:var(--good); stroke-width:2.5; }} text {{ fill:var(--ink); font-size:11px; }} .empty {{ color:var(--muted); padding:14px 0; }}
</style>
</head>
<body>
<header><h1>{safe_title}</h1><p>This is a projection over an append-only observation ledger. “Visible” here means recoverable from the capture; it does not automatically mean public to other people.</p></header>
<main>
<section class="cards" id="cards"></section>
<section class="panel"><h2>Interaction trace map</h2><div class="trace-map" id="map"></div><small class="note">The actor is emphasized only because this viewer is specifically about traces left by the capture owner. The underlying world graph remains centerless.</small></section>
<section class="panel"><h2>Observed trace timeline</h2><div class="controls" id="filters"></div><div class="timeline" id="timeline"></div></section>
<section class="panel"><h2>Alias history</h2><div class="alias-grid" id="aliases"></div><small class="note">Alias observations are timestamped by when the capture saw them. A transition does not assert the exact rename time.</small></section>
</main>
<script id="ledger" type="application/json">{payload}</script>
<script>
const L = JSON.parse(document.getElementById('ledger').textContent);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const fmt=t=>t?new Date(t).toLocaleString():'time not captured';
const cards=[['Trace events',L.trace_event_count],['Alias observations',L.alias_observation_count],['Alias transitions',L.alias_transition_count],['Entities',L.node_count]];
document.getElementById('cards').innerHTML=cards.map(([a,b])=>`<div class="card"><span>${{a}}</span><b>${{b}}</b></div>`).join('');
const actions=['all',...new Set((L.traces||[]).map(x=>x.action))]; const filters=document.getElementById('filters'); let active='all';
filters.innerHTML=actions.map(a=>`<button data-a="${{esc(a)}}" class="${{a==='all'?'active':''}}">${{esc(a.replaceAll('_',' '))}}</button>`).join('');
filters.onclick=e=>{{ if(e.target.tagName!=='BUTTON') return; active=e.target.dataset.a; [...filters.children].forEach(b=>b.classList.toggle('active',b.dataset.a===active)); drawTimeline(); }};
function drawTimeline(){{ const rows=(L.traces||[]).filter(x=>active==='all'||x.action===active); document.getElementById('timeline').innerHTML=rows.length?rows.map(x=>`<div class="event"><div class="when">${{esc(fmt(x.observed_at))}}</div><div class="dot"></div><div class="event-body"><div class="action">${{esc(x.actor)}} → ${{esc(x.action.replaceAll('_',' '))}} → ${{esc(x.target)}}</div><div class="meta">${{esc(x.trace_class)}} · capture ${{esc(x.capture)}} · entry ${{esc(x.entry_index)}}${{x.via?' · via '+esc(x.via):''}}</div></div></div>`).join(''):'<div class="empty">No trace events in this filter.</div>'; }} drawTimeline();
const grouped={{}}; for(const x of (L.alias_history||[])) (grouped[x.entity]??=[]).push(x);
document.getElementById('aliases').innerHTML=Object.entries(grouped).length?Object.entries(grouped).map(([entity,rows])=>{{ const unique=[]; for(const r of rows) if(!unique.find(x=>x.alias===r.alias)) unique.push(r); return `<div class="alias-person"><b>${{esc(entity)}}</b><div>${{unique.map(r=>`<span class="alias-chip">${{esc(r.alias)}}${{r.alias_value?' · '+esc(r.alias_value):''}}</span>`).join('')}}</div><div class="meta">${{rows.map(r=>`${{esc(r.alias)}} observed ${{esc(fmt(r.observed_at))}} via ${{esc(r.source)}}`).join(' · ')}}</div></div>`; }}).join(''):'<div class="empty">No stable-ID alias observations were captured.</div>';
function drawMap(){{ const traces=L.traces||[]; const ids=[...new Set(traces.flatMap(t=>[t.actor,t.target]))]; if(!ids.length){{document.getElementById('map').innerHTML='<div class="empty">No trace edges captured.</div>';return;}} const actors=new Set(traces.map(t=>t.actor)); const W=900,H=300,cx=450,cy=150,r=118; const pos={{}}; const actorList=[...actors]; actorList.forEach((id,i)=>{{pos[id]=[cx-230,70+i*Math.min(50,180/Math.max(1,actorList.length-1))];}}); const targets=ids.filter(id=>!actors.has(id)); targets.forEach((id,i)=>{{const a=2*Math.PI*i/Math.max(1,targets.length);pos[id]=[cx+110+Math.cos(a)*r,cy+Math.sin(a)*r];}}); const lines=traces.map(t=>{{const a=pos[t.actor],b=pos[t.target];return a&&b?`<line class="edge" x1="${{a[0]}}" y1="${{a[1]}}" x2="${{b[0]}}" y2="${{b[1]}}"/>`:''}}).join(''); const nodes=ids.map(id=>{{const p=pos[id]||[cx,cy];return `<g><circle class="node ${{actors.has(id)?'actor':''}}" cx="${{p[0]}}" cy="${{p[1]}}" r="7"/><text x="${{p[0]+10}}" y="${{p[1]+4}}">${{esc(id)}}</text></g>`}}).join(''); document.getElementById('map').innerHTML=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="Interaction trace projection">${{lines}}${{nodes}}</svg>`; }} drawMap();
</script>
</body></html>'''


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a self-contained HTML trace viewer")
    ap.add_argument("ledger", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("trace-viewer.html"))
    ap.add_argument("--title", default="Little Mouse Trace Viewer")
    args = ap.parse_args()
    with args.ledger.open("r", encoding="utf-8") as f:
        ledger = json.load(f)
    args.output.write_text(render(ledger, args.title), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

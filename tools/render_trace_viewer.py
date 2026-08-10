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
:root {{ color-scheme: light dark; --bg:#0f1115; --panel:#171a21; --ink:#eef2f7; --muted:#9aa4b2; --line:#2b3240; --accent:#8ab4f8; --good:#8bd5ca; --focus:#f2c879; }}
@media (prefers-color-scheme: light) {{ :root {{ --bg:#f5f7fb; --panel:#ffffff; --ink:#172033; --muted:#637083; --line:#dce2ec; --accent:#2457c5; --good:#157a6e; --focus:#a35b00; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:14px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--ink); }}
header {{ padding:24px max(20px,4vw) 14px; position:sticky; top:0; background:color-mix(in srgb,var(--bg) 92%,transparent); backdrop-filter:blur(12px); z-index:4; border-bottom:1px solid var(--line); }}
h1 {{ margin:0 0 6px; font-size:22px; }} header p {{ margin:0; color:var(--muted); max-width:920px; }}
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
small.note {{ color:var(--muted); display:block; margin-top:8px; }} .trace-map {{ width:100%; min-height:620px; overflow:auto; }}
svg {{ width:100%; min-width:900px; height:680px; }} .ring {{ fill:none; stroke:var(--line); stroke-width:1; stroke-dasharray:3 7; }} .edge {{ stroke:var(--line); stroke-width:1; opacity:.6; }} .node {{ fill:var(--panel); stroke:var(--accent); stroke-width:1.3; }} .actor {{ stroke:var(--good); stroke-width:2.2; }} .focus {{ stroke:var(--focus); stroke-width:4; }} text {{ fill:var(--ink); font-size:10px; }} .ring-label {{ fill:var(--muted); font-size:11px; }} .empty {{ color:var(--muted); padding:14px 0; }}
</style>
</head>
<body>
<header><h1>{safe_title}</h1><p>This is a temporary focus projection over an append-only observation ledger. The selected profile is placed at the origin for navigation only; the underlying graph remains centerless.</p></header>
<main>
<section class="cards" id="cards"></section>
<section class="panel"><h2>Profile-centered evidence map</h2><div class="controls" id="hopControls"></div><div class="trace-map" id="map"></div><small class="note">Hop distance means captured evidence-path distance, not friendship, intent, recommendation rank, or social closeness. A path through the capture owner is shown as such rather than attributed directly to the focused profile.</small></section>
<section class="panel"><h2>Observed trace timeline</h2><div class="controls" id="filters"></div><div class="timeline" id="timeline"></div></section>
<section class="panel"><h2>Alias history</h2><div class="alias-grid" id="aliases"></div><small class="note">Alias observations are timestamped by when the capture saw them. A transition does not assert the exact rename time.</small></section>
</main>
<script id="ledger" type="application/json">{payload}</script>
<script>
const L = JSON.parse(document.getElementById('ledger').textContent);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const fmt=t=>t?new Date(t).toLocaleString():'time not captured';
const focus=(L.focus&&L.focus.entity)||null;
const FV=L.focus_view||{{}};
const cards=[['Trace events',L.trace_event_count],['Focus incident traces',L.focus?.incident_trace_count??0],['Focus-connected nodes',FV.reachable_node_count??0],['Max evidence hop',FV.max_hop??0],['Alias observations',L.alias_observation_count]];
document.getElementById('cards').innerHTML=cards.map(([a,b])=>`<div class="card"><span>${{a}}</span><b>${{b}}</b></div>`).join('');

const nodeById=Object.fromEntries((L.nodes||[]).map(n=>[n.id,n]));
const graphEdges=[];
for(const t of (L.traces||[])){{
  if(t.via){{ graphEdges.push({{a:t.actor,b:t.via,action:t.action,segment:'actor→trace'}}); graphEdges.push({{a:t.via,b:t.target,action:t.action,segment:'trace→target'}}); }}
  else graphEdges.push({{a:t.actor,b:t.target,action:t.action,segment:'direct'}});
}}
const adj={{}};
for(const e of graphEdges){{(adj[e.a]??=new Set()).add(e.b);(adj[e.b]??=new Set()).add(e.a);}}
const dist={{}};
if(focus){{dist[focus]=0;const q=[focus];for(let qi=0;qi<q.length;qi++){{const n=q[qi];for(const x of (adj[n]||[]))if(dist[x]===undefined){{dist[x]=dist[n]+1;q.push(x);}}}}}}
const maxDistance=Math.max(0,...Object.values(dist));
let hopLimit=Math.min(3,maxDistance||3);
const hopControls=document.getElementById('hopControls');
if(focus){{const opts=[];for(let i=1;i<=Math.min(3,maxDistance);i++)opts.push(i);if(maxDistance>3)opts.push(maxDistance);hopControls.innerHTML=opts.map(h=>`<button data-hop="${{h}}" class="${{h===hopLimit?'active':''}}">${{h===maxDistance&&maxDistance>3?'all':h+' hop'+(h>1?'s':'')}}</button>`).join('');hopControls.onclick=e=>{{if(e.target.tagName!=='BUTTON')return;hopLimit=Number(e.target.dataset.hop);[...hopControls.children].forEach(b=>b.classList.toggle('active',Number(b.dataset.hop)===hopLimit));drawMap();drawTimeline();}};}}
else hopControls.innerHTML='<span class="meta">No focus entity stored in this ledger.</span>';

const actions=['all',...new Set((L.traces||[]).map(x=>x.action))]; const filters=document.getElementById('filters'); let active='all';
filters.innerHTML=actions.map(a=>`<button data-a="${{esc(a)}}" class="${{a==='all'?'active':''}}">${{esc(a.replaceAll('_',' '))}}</button>`).join('');
filters.onclick=e=>{{ if(e.target.tagName!=='BUTTON') return; active=e.target.dataset.a; [...filters.children].forEach(b=>b.classList.toggle('active',b.dataset.a===active)); drawTimeline(); }};
function visibleNode(id){{return !focus || (dist[id]!==undefined && dist[id]<=hopLimit);}}
function traceVisible(t){{return visibleNode(t.actor)&&visibleNode(t.target)&&(!t.via||visibleNode(t.via));}}
function drawTimeline(){{ const rows=(L.traces||[]).filter(x=>(active==='all'||x.action===active)&&traceVisible(x)); document.getElementById('timeline').innerHTML=rows.length?rows.map(x=>`<div class="event"><div class="when">${{esc(fmt(x.observed_at))}}</div><div class="dot"></div><div class="event-body"><div class="action">${{esc(x.actor)}} → ${{esc(x.action.replaceAll('_',' '))}} → ${{esc(x.target)}}</div><div class="meta">${{esc(x.trace_class)}} · capture ${{esc(x.capture)}} · entry ${{esc(x.entry_index)}}${{x.via?' · via '+esc(x.via):''}}</div></div></div>`).join(''):'<div class="empty">No trace events in this focus radius and filter.</div>'; }}

const grouped={{}}; for(const x of (L.alias_history||[])) (grouped[x.entity]??=[]).push(x);
const aliasEntries=Object.entries(grouped).sort(([a],[b])=>a===focus?-1:b===focus?1:a.localeCompare(b));
document.getElementById('aliases').innerHTML=aliasEntries.length?aliasEntries.map(([entity,rows])=>{{ const unique=[]; for(const r of rows) if(!unique.find(x=>x.alias===r.alias)) unique.push(r); return `<div class="alias-person"><b>${{esc(entity)}}${{entity===focus?' · focus':''}}</b><div>${{unique.map(r=>`<span class="alias-chip">${{esc(r.alias)}}${{r.alias_value?' · '+esc(r.alias_value):''}}</span>`).join('')}}</div><div class="meta">${{rows.map(r=>`${{esc(r.alias)}} observed ${{esc(fmt(r.observed_at))}} via ${{esc(r.source)}}`).join(' · ')}}</div></div>`; }}).join(''):'<div class="empty">No stable-ID alias observations were captured.</div>';

function nodeLabel(id){{const n=nodeById[id]||{{}};if(id===focus)return 'FOCUS';if(n.is_capture_actor)return 'capture owner';if(n.type==='person')return id.slice(0,18);if(n.type==='comment')return 'comment';if(n.type==='media')return 'media';return n.type||id.slice(0,12);}}
function drawMap(){{
  if(!focus){{document.getElementById('map').innerHTML='<div class="empty">No focus entity is stored in this ledger.</div>';return;}}
  const ids=Object.keys(dist).filter(id=>dist[id]<=hopLimit);
  if(!ids.length){{document.getElementById('map').innerHTML='<div class="empty">No focused evidence paths captured.</div>';return;}}
  const W=1100,H=680,cx=550,cy=340; const pos={{[focus]:[cx,cy]}};
  const rings={{}}; for(const id of ids){{const d=dist[id];if(d>0)(rings[d]??=[]).push(id);}}
  for(const [dStr,ringIdsRaw] of Object.entries(rings)){{const d=Number(dStr);const ringIds=[...ringIdsRaw].sort();const base=95+d*105;for(let i=0;i<ringIds.length;i++){{const id=ringIds[i];const band=Math.floor(i/50);const r=base+band*24;const slot=i%50;const slots=Math.min(50,ringIds.length-band*50);const a=-Math.PI/2+2*Math.PI*slot/Math.max(1,slots);pos[id]=[cx+Math.cos(a)*r,cy+Math.sin(a)*r];}}}}
  const ringSvg=Object.keys(rings).map(d=>{{const r=95+Number(d)*105;return `<circle class="ring" cx="${{cx}}" cy="${{cy}}" r="${{r}}"/><text class="ring-label" x="${{cx+r+4}}" y="${{cy}}">hop ${{d}}</text>`}}).join('');
  const edgeSvg=graphEdges.filter(e=>visibleNode(e.a)&&visibleNode(e.b)).map(e=>{{const a=pos[e.a],b=pos[e.b];return a&&b?`<line class="edge" x1="${{a[0]}}" y1="${{a[1]}}" x2="${{b[0]}}" y2="${{b[1]}}"><title>${{esc(e.action+' · '+e.segment)}}</title></line>`:''}}).join('');
  const nodes=ids.map(id=>{{const p=pos[id];const n=nodeById[id]||{{}};const cls=`node ${{n.is_capture_actor?'actor ':''}}${{id===focus?'focus':''}}`;const label=nodeLabel(id);const showLabel=id===focus||n.is_capture_actor||n.type==='person';return `<g><circle class="${{cls}}" cx="${{p[0]}}" cy="${{p[1]}}" r="${{id===focus?10:5}}"><title>${{esc(id+' · '+(n.type||'entity')+' · hop '+dist[id])}}</title></circle>${{showLabel?`<text x="${{p[0]+9}}" y="${{p[1]+3}}">${{esc(label)}}</text>`:''}}</g>`}}).join('');
  document.getElementById('map').innerHTML=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="Profile-centered interaction trace projection">${{ringSvg}}${{edgeSvg}}${{nodes}}</svg>`;
}}
drawMap();drawTimeline();
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

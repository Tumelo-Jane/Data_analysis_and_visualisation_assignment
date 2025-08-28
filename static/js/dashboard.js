// Plotly front-end logic
let state = { a: "gdp", b: "inflation", start: 1990, end: 2023, period: "all" };

const els = {
  a: () => document.getElementById("indicatorA"),
  b: () => document.getElementById("indicatorB"),
  start: () => document.getElementById("startYear"),
  end: () => document.getElementById("endYear"),
  period: () => document.getElementById("period"),
  kpiAName: () => document.getElementById("kpiAName"),
  kpiBName: () => document.getElementById("kpiBName"),
  kpiAMean: () => document.getElementById("kpiAMean"),
  kpiBMean: () => document.getElementById("kpiBMean"),
  kpiAOther: () => document.getElementById("kpiAOther"),
  kpiBOther: () => document.getElementById("kpiBOther"),
  downloadCSV: () => document.getElementById("downloadCSV"),
};
const fmt = (n) => (n===null||n===undefined) ? "–" : Number(n).toLocaleString(undefined,{maximumFractionDigits:3});

async function getJSON(url, params) {
  const u = new URL(url, window.location.origin);
  Object.entries(params||{}).forEach(([k,v])=>{ if(v!=="" && v!==null && v!==undefined) u.searchParams.set(k,v); });
  const r = await fetch(u); if(!r.ok) throw new Error(`GET ${u} failed`); return r.json();
}
const fetchSeries = (indicator, start, end, period) => getJSON("/api/series", {indicator,start,end,period});
const fetchPairs  = (x,y,start,end,period) => getJSON("/api/pairs",  {x,y,start,end,period});

function updateKPIs(aName, aKpi, bName, bKpi){
  els.kpiAName().textContent = `${aName} — Mean`;
  els.kpiAMean().textContent = fmt(aKpi.mean);
  els.kpiAOther().textContent = `Std ${fmt(aKpi.std)} | Min ${fmt(aKpi.min)} | Max ${fmt(aKpi.max)}`;
  els.kpiBName().textContent = `${bName} — Mean`;
  els.kpiBMean().textContent = fmt(bKpi.mean);
  els.kpiBOther().textContent = `Std ${fmt(bKpi.std)} | Min ${fmt(bKpi.min)} | Max ${fmt(bKpi.max)}`;
}
const unionYears = (a,b) => Array.from(new Set([...(a||[]), ...(b||[])])).sort((x,y)=>x-y);
const seriesToAligned = (s, years) => { const m=new Map((s.years||[]).map((y,i)=>[y,s.values[i]])); return years.map(y=>m.has(y)?m.get(y):null); };
const yoyToAligned    = (s, years) => { const m=new Map((s.years||[]).map((y,i)=>[y,s.yoy[i]]));    return years.map(y=>m.has(y)?m.get(y):null); };
const csvFromFiltered = (years,aVals,bVals,aName,bName)=>[["Year",aName,bName],...years.map((y,i)=>[y,aVals[i]??"",bVals[i]??""])].map(r=>r.join(",")).join("\n");

function plotLine(years,aVals,bVals,aName,bName){
  const A={x:years,y:aVals,name:aName,mode:"lines+markers",yaxis:"y1"};
  const B={x:years,y:bVals,name:bName,mode:"lines+markers",yaxis:"y2"};
  Plotly.newPlot("lineChart",[A,B],{margin:{l:50,r:40,t:10,b:40},hovermode:"x unified",yaxis:{title:aName},yaxis2:{title:bName,overlaying:"y",side:"right"},legend:{orientation:"h"}},{responsive:true});
}
function plotBar(years,aYoY,bYoY,aName,bName){
  const A={x:years,y:aYoY,type:"bar",name:`${aName} YoY`};
  const B={x:years,y:bYoY,type:"bar",name:`${bName} YoY`};
  Plotly.newPlot("barChart",[A,B],{barmode:"group",margin:{l:50,r:10,t:10,b:40},yaxis:{title:"Year-over-Year Δ",zeroline:true},legend:{orientation:"h"}},{responsive:true});
}
function plotScatter(points,line,aName,bName){
  const S={mode:"markers",type:"scatter",x:points.map(p=>p.x),y:points.map(p=>p.y),text:points.map(p=>`Year ${p.year}`),name:`${aName} vs ${bName}`};
  const traces=[S];
  if(line){ traces.push({mode:"lines",type:"scatter",x:[line.x_min,line.x_max],y:[line.y_min,line.y_max],name:"Trend"}); }
  Plotly.newPlot("scatterChart",traces,{margin:{l:50,r:10,t:10,b:40},xaxis:{title:aName},yaxis:{title:bName},legend:{orientation:"h"}},{responsive:true});
}

async function apply(){
  state.a=els.a().value; state.b=els.b().value;
  state.start=els.start().value||""; state.end=els.end().value||""; state.period=els.period().value;
  const [aSeries,bSeries,pair]=await Promise.all([fetchSeries(state.a,state.start,state.end,state.period), fetchSeries(state.b,state.start,state.end,state.period), fetchPairs(state.a,state.b,state.start,state.end,state.period)]);
  const years=unionYears(aSeries.years,bSeries.years);
  const aVals=seriesToAligned(aSeries,years), bVals=seriesToAligned(bSeries,years);
  const aYoY=yoyToAligned(aSeries,years),    bYoY=yoyToAligned(bSeries,years);
  const nameA=state.a==="gdp"?"GDP":"Inflation", nameB=state.b==="gdp"?"GDP":"Inflation";
  plotLine(years,aVals,bVals,nameA,nameB); plotBar(years,aYoY,bYoY,nameA,nameB); plotScatter(pair.points||[],pair.line||null,nameA,nameB);
  updateKPIs(nameA,aSeries.kpis,nameB,bSeries.kpis);
  const csv=csvFromFiltered(years,aVals,bVals,nameA,nameB); const blob=new Blob([csv],{type:"text/csv"}); const url=URL.createObjectURL(blob);
  const a=els.downloadCSV(); a.href=url; a.download=`filtered_${nameA}_${nameB}.csv`;
}
function reset(){ window.location.reload(); }
document.addEventListener("DOMContentLoaded",()=>{ document.getElementById("applyBtn").addEventListener("click",apply); document.getElementById("resetBtn").addEventListener("click",reset); apply().catch(console.error); });

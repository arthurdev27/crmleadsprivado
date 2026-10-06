import os, hashlib, hmac
from typing import Optional
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app=FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","")
SESSION_SECRET=os.getenv("SESSION_SECRET","change-this")
SUPABASE_URL=os.getenv("SUPABASE_URL","").rstrip("/")
SUPABASE_KEY=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY","")
SUPABASE_TABLE=os.getenv("SUPABASE_TABLE","leads")
OVERPASS_URL=os.getenv("OVERPASS_URL","https://overpass-api.de/api/interpreter")

def token(p): return hmac.new(SESSION_SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
def auth(r):
    return not ADMIN_PASSWORD or hmac.compare_digest(r.cookies.get("crm_session",""), token(ADMIN_PASSWORD))
def hdr(): return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json"}

@app.get("/")
async def home(): return FileResponse("public/index.html")

@app.get("/api/health")
async def health(): return {"ok":True,"supabase":bool(SUPABASE_URL and SUPABASE_KEY)}

@app.get("/api/me")
async def me(request:Request): return {"authenticated":auth(request)}

class Login(BaseModel): password:str
@app.post("/api/login")
async def login(body:Login,response:Response):
    if ADMIN_PASSWORD and not hmac.compare_digest(body.password,ADMIN_PASSWORD): raise HTTPException(401,"Senha inválida")
    response.set_cookie("crm_session",token(body.password),httponly=True,samesite="lax",secure=True,max_age=604800)
    return {"ok":True}
@app.post("/api/logout")
async def logout(response:Response):
    response.delete_cookie("crm_session"); return {"ok":True}

async def db_get():
    if not SUPABASE_URL or not SUPABASE_KEY: return []
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?order=score.desc&limit=500",headers=hdr()); r.raise_for_status(); return r.json()
async def db_upsert(rows):
    if not SUPABASE_URL or not SUPABASE_KEY or not rows: return
    async with httpx.AsyncClient(timeout=25) as c:
        r=await c.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",headers={**hdr(),"Prefer":"resolution=merge-duplicates,return=minimal"},json=rows); r.raise_for_status()
async def db_patch(i,data):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.patch(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?id=eq.{i}",headers=hdr(),json=data); r.raise_for_status()

@app.get("/api/leads")
async def leads(request:Request):
    if not auth(request): raise HTTPException(401,"Não autenticado")
    return await db_get()

CATS={"hamburgueria":'["amenity"="fast_food"]["cuisine"~"burger|hamburger",i]',
"pizzaria":'["amenity"="fast_food"]["cuisine"~"pizza",i]',
"restaurante":'["amenity"="restaurant"]',"lanchonete":'["amenity"="fast_food"]',
"pastelaria":'["cuisine"~"pastel",i]',"açaí":'["cuisine"~"açaí|acai",i]',
"salão de beleza":'["shop"="hairdresser"]',"barbearia":'["shop"="hairdresser"]',
"cabeleireiro":'["shop"="hairdresser"]',"estética":'["shop"="beauty"]'}

def normalize(e,cat,city):
    t=e.get("tags",{}); lat=e.get("lat",e.get("center",{}).get("lat")); lon=e.get("lon",e.get("center",{}).get("lon"))
    name=t.get("name") or t.get("brand")
    if not name: return None
    phone=t.get("phone") or t.get("contact:phone") or t.get("contact:mobile") or ""
    website=t.get("website") or t.get("contact:website") or ""
    insta=t.get("contact:instagram") or t.get("instagram") or ""
    maps=f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" if lat and lon else ""
    score=(40 if not website else 0)+(30 if phone else 0)+(10 if insta else 0)
    return {"id":f"osm-{e['type']}-{e['id']}","place_id":f"osm-{e['type']}-{e['id']}","name":name,
    "category":cat,"address":(t.get("addr:street","")+" "+t.get("addr:housenumber","")).strip(),"city":city,"state":"RJ",
    "phone":phone,"website":website,"instagram":insta,"facebook":t.get("contact:facebook") or "",
    "tiktok":t.get("contact:tiktok") or "","maps_url":maps,"photo_url":"","rating":None,"reviews":None,
    "score":score,"status":"Novo","notes":""}

@app.get("/api/leads/search")
async def search(request:Request,category:str="hamburgueria",city:str="Rio das Ostras",amount:int=20):
    if not auth(request): raise HTTPException(401,"Não autenticado")
    tag=CATS.get(category,CATS["restaurante"])
    q=f'[out:json][timeout:30];area["name"="{city}"]["boundary"="administrative"]->.a;(nwr(area.a){tag};);out center tags;'
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            r=await c.post(OVERPASS_URL,data={"data":q}); r.raise_for_status(); els=r.json().get("elements",[])
    except Exception as e: raise HTTPException(502,f"Falha na fonte gratuita: {e}")
    out=[]
    for e in els:
        x=normalize(e,category,city)
        if x and x["phone"] and not x["website"]: out.append(x)
    out.sort(key=lambda x:(x["score"],x["name"]),reverse=True)
    out=out[:max(1,min(amount,50))]
    await db_upsert(out)
    return out

class Patch(BaseModel):
    status:Optional[str]=None; notes:Optional[str]=None; instagram:Optional[str]=None; facebook:Optional[str]=None; tiktok:Optional[str]=None; website:Optional[str]=None
@app.patch("/api/leads/{lead_id}")
async def patch(lead_id:str,body:Patch,request:Request):
    if not auth(request): raise HTTPException(401,"Não autenticado")
    await db_patch(lead_id,{k:v for k,v in body.model_dump().items() if v is not None}); return {"ok":True}

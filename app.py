from flask import Flask, jsonify
from main import collect
from profit_ranker import rank_leads
from queue_store import enqueue, list_queue

app=Flask(__name__)

@app.get("/")
def home():
    return {"service":"Job + Freelance Hunter","status":"ok",
            "jobs":"/jobs","freelance":"/freelance","queue":"/queue"}

@app.get("/jobs")
def jobs():
    return jsonify(collect())

@app.get("/freelance")
def freelance():
    data=collect()
    leads=[x for x in data.get("items",[]) if x.get("category","").startswith("freelance")]
    ranked=rank_leads(leads)
    for lead in ranked:
        enqueue(lead)
    return jsonify({"count":len(ranked),"items":ranked})

@app.get("/queue")
def queue():
    return jsonify({"items":list_queue()})

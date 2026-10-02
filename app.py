from flask import Flask, jsonify
from main import collect
app=Flask(__name__)
@app.get("/")
def home(): return {"service":"Job + Freelance Hunter","status":"ok","jobs":"/jobs"}
@app.get("/jobs")
def jobs(): return jsonify(collect())

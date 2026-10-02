"""One-pass autonomous hunter worker."""
from main import collect
from profit_ranker import rank_leads
from proposal_writer import make_proposal
from application_dispatcher import dispatch
from queue_store import enqueue, set_state

def run():
    data=collect()
    leads=[x for x in data.get("items",[]) if str(x.get("category","")).startswith("freelance")]
    ranked=rank_leads(leads)
    stats={"found":len(leads),"ranked":len(ranked),"submitted":0,"shortlisted":0,"needs_confirmation":0,"skipped":0,"failed":0}
    results=[]
    for lead in ranked:
        lid=enqueue(lead)
        try:
            set_state(lid,"SHORTLISTED")
            proposal=make_proposal(lead)
            result=dispatch(lead,proposal)
            state=result["status"]
            set_state(lid,state)
            key=state.lower()
            if key in stats: stats[key]+=1
            results.append({"id":lid,"title":lead.get("title"),"score":lead.get("profit_score"),**result})
        except Exception as e:
            set_state(lid,"FAILED"); stats["failed"]+=1
            results.append({"id":lid,"title":lead.get("title"),"status":"FAILED","reason":type(e).__name__})
    return {"stats":stats,"results":results}

if __name__=="__main__":
    import json
    print(json.dumps(run(),ensure_ascii=False,indent=2))

"""One-pass autonomous freelance hunter worker."""
from freelance_sources import collect_freelance, collect_prolinker
from freelancehunt_adapter import collect_freelancehunt
from profit_ranker import rank_leads
from proposal_writer import make_proposal
from application_dispatcher import dispatch
from queue_store import enqueue, set_state

def run():
    # Freelance has its own pipeline so job-board results can never crowd it out.
    leads=collect_freelance() + collect_prolinker()
    try: leads += collect_freelancehunt()
    except Exception: pass
    ranked=rank_leads(leads)
    stats={"found":len(leads),"ranked":len(ranked),"submitted":0,"shortlisted":0,
           "needs_confirmation":0,"skipped":0,"failed":0}
    results=[]
    for lead in ranked:
        lid=enqueue(lead)
        try:
            set_state(lid,"SHORTLISTED")
            proposal=make_proposal(lead)
            result=dispatch(lead,proposal)
            state=result["status"]; set_state(lid,state)
            key=state.lower()
            if key in stats: stats[key]+=1
            results.append({"id":lid,"title":lead.get("title"),
                            "source":lead.get("source"),"url":lead.get("url"),
                            "score":lead.get("profit_score"),
                            "matched_skills":lead.get("matched_skills",[]),
                            "proposal":proposal,**result})
        except Exception as e:
            set_state(lid,"FAILED"); stats["failed"]+=1
            results.append({"id":lid,"title":lead.get("title"),
                            "status":"FAILED","reason":type(e).__name__})
    return {"stats":stats,"results":results}

if __name__=="__main__":
    import json
    print(json.dumps(run(),ensure_ascii=False,indent=2))

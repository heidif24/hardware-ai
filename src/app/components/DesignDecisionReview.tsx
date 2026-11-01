"use client";
export type DecisionOption={id:string;label:string;description:string;advantages:string[];tradeoffs:string[]};
export type Decision={id:string;title:string;context:string;recommended:string;reason:string;options:DecisionOption[];requires_confirmation:boolean};
export type DecisionSelections=Record<string,string>;
export type DecisionNotes=Record<string,string>;
export default function DesignDecisionReview({decisions,selections,notes,onSelect,onNote}:{decisions:Decision[];selections:DecisionSelections;notes:DecisionNotes;onSelect:(id:string,value:string)=>void;onNote:(id:string,value:string)=>void}){
 return <section className="decision-review">
  <div className="decision-intro"><span className="section-kicker">DESIGN BASIS · USER REVIEW</span><h3>Review the engineering choices</h3><p>These are provisional engineering recommendations, not purchased or verified components. Choose the option that best matches your product, or add a clarification for the engineering team. Your selections will be included in the project handover.</p></div>
  {decisions.map((d,index)=>{const selected=selections[d.id]||d.recommended;const choice=d.options.find(o=>o.id===selected)||d.options[0];return <article className="decision-card" key={d.id}>
   <div className="decision-card-head"><span className="decision-number">{String(index+1).padStart(2,"0")}</span><div><h4>{d.title}</h4><p>{d.context}</p></div><span className="recommended-label">RECOMMENDED</span></div>
   <div className="decision-reason"><strong>Why this is recommended</strong><p>{d.reason}</p></div>
   <div className="decision-options">{d.options.map(o=><label className={selected===o.id?"decision-option selected":"decision-option"} key={o.id}><input type="radio" name={d.id} value={o.id} checked={selected===o.id} onChange={()=>onSelect(d.id,o.id)}/><span className="decision-option-copy"><strong>{o.label}{o.id===d.recommended?" · Recommended":""}</strong><small>{o.description}</small><small><b>Advantages:</b> {o.advantages.join(" · ")}</small><small><b>Trade-offs:</b> {o.tradeoffs.join(" · ")}</small></span></label>)}</div>
   {choice&&<div className="selected-choice">Selected basis: <strong>{choice.label}</strong></div>}
   <label className="decision-note-label" htmlFor={"note-"+d.id}>Your notes or clarification (optional)</label><textarea id={"note-"+d.id} rows={2} value={notes[d.id]||""} onChange={e=>onNote(d.id,e.target.value)} placeholder="Add your preference, constraints, questions or reasons for choosing another option…"/>
  </article>})}
 </section>;
}
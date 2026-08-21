from __future__ import annotations
import json, os, re
from typing import Any
from .deterministic import render
from ..models import ComposedMessage

SYSTEM_PROMPT = '''You are Vera, a merchant-growth assistant for magicpin.\n\nCompose exactly one concise WhatsApp message from the supplied facts. Never invent facts. Every factual claim must be directly supported by the input. The trigger is the reason for messaging now and must be reflected. Match the category voice and merchant language preference. Use one primary CTA only. Merchant-facing messages use send_as=vera; customer-facing messages use send_as=merchant_on_behalf. Preserve the supplied suppression_key exactly. Avoid hype, generic discounts, multiple CTAs, internal jargon, and forbidden category vocabulary. Return ONLY JSON with body, cta, send_as, suppression_key, rationale.'''


def _extract_json(text: str) -> dict[str,Any]:
    m = re.search(r'\{.*\}', text, flags=re.S)
    if not m: raise ValueError('LLM did not return JSON')
    return json.loads(m.group(0))


def _llm_compose(packet: dict[str,Any]) -> dict[str,Any] | None:
    provider = os.getenv('LLM_PROVIDER','').lower()
    key = os.getenv('LLM_API_KEY','')
    if not provider or not key: return None
    prompt = json.dumps(packet, ensure_ascii=False, indent=2)
    try:
        if provider == 'gemini':
            import urllib.request
            model = os.getenv('LLM_MODEL','gemini-2.0-flash')
            payload = {'contents':[{'parts':[{'text':SYSTEM_PROMPT+'\n\nFACTS:\n'+prompt}]}], 'generationConfig':{'temperature':0,'maxOutputTokens':700,'responseMimeType':'application/json'}}
            req=urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=6) as r: data=json.loads(r.read().decode())
            text=data['candidates'][0]['content']['parts'][0]['text']
            return _extract_json(text)
        if provider in {'openai','openrouter','deepseek','groq'}:
            import urllib.request
            urls={'openai':'https://api.openai.com/v1/chat/completions','openrouter':'https://openrouter.ai/api/v1/chat/completions','deepseek':'https://api.deepseek.com/v1/chat/completions','groq':'https://api.groq.com/openai/v1/chat/completions'}
            models={'openai':'gpt-4o-mini','openrouter':'openai/gpt-4o-mini','deepseek':'deepseek-chat','groq':'llama-3.3-70b-versatile'}
            model=os.getenv('LLM_MODEL',models[provider])
            payload={'model':model,'messages':[{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':prompt}],'temperature':0,'max_tokens':700,'response_format':{'type':'json_object'}}
            headers={'Content-Type':'application/json','Authorization':f'Bearer {key}'}
            if provider=='openrouter': headers['HTTP-Referer']='https://magicpin.com'
            req=urllib.request.Request(urls[provider],data=json.dumps(payload).encode(),headers=headers)
            with urllib.request.urlopen(req, timeout=6) as r: data=json.loads(r.read().decode())
            return _extract_json(data['choices'][0]['message']['content'])
    except Exception:
        return None
    return None


def validate(result: dict[str,Any], category: dict, trigger: dict, customer: dict|None) -> dict[str,Any]:
    required={'body','cta','send_as','suppression_key','rationale'}
    if not required.issubset(result): raise ValueError('missing output fields')
    if result['cta'] not in {'binary_yes_no','binary_confirm_cancel','multi_choice_slot','open_ended','none'}: raise ValueError('invalid CTA')
    expected='merchant_on_behalf' if customer else 'vera'
    if result['send_as'] != expected: raise ValueError('wrong send_as')
    if trigger.get('suppression_key') and result['suppression_key'] != trigger['suppression_key']: raise ValueError('suppression key changed')
    body=str(result['body']).strip()
    if not body: raise ValueError('empty body')
    taboo=[str(x).lower() for x in category.get('voice',{}).get('vocab_taboo',[])]
    lower=body.lower()
    if any(x in lower for x in taboo): raise ValueError('taboo phrase')
    return {'body':body,'cta':result['cta'],'send_as':result['send_as'],'suppression_key':result['suppression_key'],'rationale':str(result['rationale'])[:1000]}


def compose(category: dict, merchant: dict, trigger: dict, customer: dict|None=None) -> dict[str,Any]:
    deterministic=render(category,merchant,trigger,customer)
    packet={'category':category,'merchant':merchant,'trigger':trigger,'customer':customer,'deterministic_candidate':deterministic}
    llm=_llm_compose(packet)
    if llm is not None:
        try: return validate(llm,category,trigger,customer)
        except Exception: pass
    return validate(deterministic,category,trigger,customer)
